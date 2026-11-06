"""Después de tu partida: su revisión (cuando Riot la publica), los LP ganados o perdidos y los clips de tus muertes."""

import datetime
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from . import analisis as an
from . import clips
from . import duelos as du
from . import revision as rv
from .base_duelos import BaseDuelos
from .cache import Cache
from .comparador import Comparador
from .constantes import LIGA_COLA, SOLO_DUO
from .ddragon import Datos
from .grabacion import buscar_ffmpeg, inicio_de_series
from .partidas import Partidas
from .riot import Cliente, ErrorRiot
from .tipos import Json, Linea, Panel, Resultado, Revision

logger = logging.getLogger(__name__)

# Revisiones que se guardan en el índice (las más recientes).
MAX_REVISIONES = 100
CLAVES_INDICE = ("id", "fecha", "cola", "duracion", "gana", "campeon", "campeon_id", "kda", "icono")


def desfase(carpeta: Path | None, inicio_ms: int | None) -> dict[int, float] | None:
    """Por cada serie de la grabación, segundos grabados antes del 0:00 de la partida: {serie: s}, o None.

    La grabación empieza en la pantalla de carga; si ffmpeg se relanza a media partida (p. ej. al cambiar la
    resolución), esa serie empieza ya jugando y su desfase es negativo.
    """
    if not carpeta or not inicio_ms:
        return None
    series = inicio_de_series(carpeta)
    if not series:
        return None
    return {n: round(inicio_ms / 1000 - t) for n, t in series.items()}


class Revisor:
    """Revisa tus partidas al acabar y guarda las revisiones en la caché (y junto a la grabación, si la hay).

    cuentas: tus cuentas (puuid -> 'Nombre#TAG'). en_partida: si se está jugando otra (los clips esperan a que acabe).
    """

    def __init__(
        self,
        cache: Cache,
        cliente: Cliente,
        datos: Datos,
        duelos: BaseDuelos,
        comparador: Comparador,
        cuentas: dict[str, str],
        partidas: Partidas,
        en_partida: Callable[[], bool],
    ) -> None:
        self.cache = cache
        self.cliente = cliente
        self.datos = datos
        self.duelos = duelos
        self.comparador = comparador
        self.cuentas = cuentas
        self.partidas = partidas
        self._en_partida = en_partida
        self.revisando = 0  # revisiones esperando a que Riot publique la partida (no actualizar mientras)
        self.ultima: str | None = None  # id de la última revisión post-partida terminada

    def en_segundo_plano(self, game_id: int, puuid: str, panel: Panel, carpeta: Path | None) -> None:
        threading.Thread(target=self.revisar, args=(game_id, puuid, panel, carpeta), name="revision", daemon=True).start()

    def revisar(
        self, game_id: int, puuid: str, panel: Panel | None, carpeta: Path | None, intentos: int = 20, pausa: float = 60
    ) -> Revision | None:
        """Espera a que Riot publique la partida (tarda unos minutos), la revisa y la guarda."""
        self.revisando += 1
        try:
            return self._revisar_partida(game_id, puuid, panel, carpeta, intentos, pausa)
        finally:
            self.revisando -= 1

    def _revisar_partida(
        self, game_id: int, puuid: str, panel: Panel | None, carpeta: Path | None, intentos: int, pausa: float
    ) -> Revision | None:
        # El host es "euw1.api.riotgames.com"; el id de la partida empieza por "EUW1_".
        id_ = f"{self.cliente.plataforma.split('.')[0].upper()}_{game_id}"
        crudo: Json | None = None
        linea: Json | None = None
        for intento in range(intentos):
            try:
                crudo = self.cliente.partida(id_, fondo=True)
                linea = self.cliente.linea(id_, fondo=True) if crudo else None
            except ErrorRiot as e:
                logger.warning("Revisión de %s: %s", id_, e)
            if crudo and linea:
                break
            if intento < intentos - 1:
                time.sleep(pausa)
        if not (crudo and linea):
            return None
        red = an.reducir_partida(crudo)
        if red["remake"]:
            return None
        id_ = red["id"]
        self.cache.guardar_partida(red)
        inicio = crudo["info"].get("gameStartTimestamp")
        desfase_s = desfase(carpeta, inicio)
        rev = rv.revisar(red, rv.reducir_linea_completa(linea), puuid, self.datos.nombre, panel, desfase_s)
        if not rev:
            return None
        rev["referencia"] = self._referencia(crudo, linea, puuid)
        rev["lp"] = self.cambio_lp(puuid, panel, red["cola"])
        rev["carpeta"] = str(carpeta) if carpeta else ""
        rev["icono"] = self.datos.icono(rev["campeon_id"])
        self.guardar(rev)
        if carpeta:
            try:
                (carpeta / "panel.json").write_text(json.dumps(panel, ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError as e:
                logger.warning("No se pudo guardar el panel junto a la grabación: %s", e)
        self.ultima = id_
        logger.info("Revisión lista: %s", id_)
        if carpeta and desfase_s is not None and rev["muertes"]:
            threading.Thread(target=self.hacer_clips, args=(rev["id"], desfase_s), name="clips", daemon=True).start()
        return rev

    def guardar(self, rev: Revision) -> None:
        self.cache.kv_set(f"revision:{rev['id']}", rev)
        indice = [r for r in (self.cache.kv_get("revisiones") or []) if r["id"] != rev["id"]]
        fila = {k: rev[k] for k in CLAVES_INDICE}
        fila["lp"] = (rev.get("lp") or {}).get("cambio")
        indice.insert(0, fila)
        indice.sort(key=lambda r: r["fecha"], reverse=True)
        self.cache.kv_set("revisiones", indice[:MAX_REVISIONES])
        if rev.get("carpeta"):
            try:
                (Path(rev["carpeta"]) / "revision.json").write_text(
                    json.dumps(rev, ensure_ascii=False, indent=1), encoding="utf-8"
                )
            except OSError as e:
                logger.warning("No se pudo guardar la revisión junto a la grabación: %s", e)

    def cambio_lp(self, puuid: str, panel: Panel | None, cola: int) -> Json | None:
        """Tu liga después de la partida y, si la de antes es de justo una partida atrás, los LP ganados o perdidos."""
        tipo = LIGA_COLA.get(cola)
        if not tipo:
            return None
        try:
            entradas = self.cliente.ligas(puuid) or []
        except ErrorRiot as e:
            logger.warning("No se pudo leer la liga tras la partida: %s", e)
            return None
        liga = next((x for x in entradas if x.get("queueType") == tipo), None)
        if not liga:
            return None
        despues = {
            "nivel": liga.get("tier", ""),
            "rank": liga.get("rank", ""),
            "lp": liga.get("leaguePoints", 0),
            "v": liga.get("wins", 0),
            "d": liga.get("losses", 0),
        }
        out: Json = {"lp": despues["lp"], "nivel": despues["nivel"].lower(), "rank": despues["rank"]}
        yo = next((f for f in ((panel or {}).get("equipos") or {}).get("aliado", []) if f.get("soy_yo")), None)
        antes = ((yo or {}).get("liga") or {}).get("solo" if cola == SOLO_DUO else "flex")
        if antes and "rank" in antes and despues["v"] + despues["d"] - antes["v"] - antes["d"] == 1:
            a = an.valor_liga(antes["nivel"], antes["rank"], antes["lp"])
            b = an.valor_liga(despues["nivel"], despues["rank"], despues["lp"])
            if a is not None and b is not None:
                out["cambio"] = b - a
        return out

    def hacer_clips(self, id_: str, desfase_s: Mapping[int, float]) -> None:
        """Recorta cada muerte de la grabación. Si empieza otra partida, espera a que acabe para no quitarle rendimiento."""
        ffmpeg = buscar_ffmpeg()
        if not ffmpeg:
            return
        rev = self.una(id_)
        if not rev:
            return
        for i, m in enumerate(rev["muertes"]):
            while self._en_partida():
                time.sleep(30)
            ruta = clips.recortar(ffmpeg, rev["carpeta"], i, m, desfase_s)
            if ruta:
                m["clip"] = str(ruta)
        if any(m.get("clip") for m in rev["muertes"]):
            self.guardar(rev)
            logger.info("Clips de las muertes de %s listos", id_)

    def abrir_clip(self, id_: str, i: Any) -> Resultado:
        rev = self.una(id_) or {}
        muertes = rev.get("muertes") or []
        ruta = Path(muertes[i].get("clip") or "") if isinstance(i, int) and 0 <= i < len(muertes) else None
        if not ruta or not ruta.is_file():
            return {"ok": False, "error": "Ese clip no está (¿se borró la grabación?)."}
        os.startfile(ruta)
        return {"ok": True}

    def abrir_carpeta(self, id_: str) -> Resultado:
        rev = self.una(id_) or {}
        carpeta = Path(rev.get("carpeta") or "")
        if not rev.get("carpeta") or not carpeta.is_dir():
            return {"ok": False, "error": "Esa partida no tiene grabación."}
        os.startfile(carpeta)
        return {"ok": True}

    def rellenar(self) -> None:
        """Las revisiones de antes del mapa de muertes no guardaban dónde moriste: se completa una vez."""
        if self.cache.kv_get("relleno_muertes_v1"):
            return
        for fila in self.cache.kv_get("revisiones") or []:
            rev = self.una(fila["id"])
            if not rev or "equipo" in rev:
                continue
            partida = self.cache.partida(rev["id"])
            yo = next((j for j in (partida or {}).get("jug", []) if j["puuid"] in self.cuentas), None)
            if not yo:
                continue
            try:
                linea = self.cliente.linea(rev["id"], fondo=True)
            except ErrorRiot as e:
                logger.warning("Relleno de %s: %s", rev["id"], e)
                return
            if not linea:
                continue
            kills = {k[0]: k for k in rv.reducir_linea_completa(linea)["kills"] if k[4] == yo["pid"]}
            for m in rev["muertes"]:
                k = kills.get(m.get("ms"))
                if k:
                    m["x"], m["y"] = k[1], k[2]
            rev["equipo"] = yo["equipo"]
            self.cache.kv_set(f"revision:{rev['id']}", rev)
        self.cache.kv_set("relleno_muertes_v1", True)

    def _referencia(self, crudo: Json, linea: Linea | Json, puuid: str) -> Json | None:
        try:
            registros = du.extraer(crudo, linea, self.datos.legendarios)
        except (KeyError, TypeError, IndexError):
            return None
        mio = next((r for r in registros if r.get("puuid") == puuid), None)
        if registros:
            self.duelos.guardar(crudo["metadata"]["matchId"], [dict(r) for r in registros])
        if not mio:
            return None
        ref, nombre = self.comparador.referencia(mio["a"], mio["pos"], mio["b"])
        return du.comparar([mio], ref, mio["pos"], nombre, minimo=3)

    def lista(self) -> Json:
        """Tus revisiones guardadas, las tendencias de la temporada y el mapa de tus muertes."""

        def hora(ms: int) -> int:
            return datetime.datetime.fromtimestamp(ms / 1000).hour

        lista = self.cache.kv_get("revisiones") or []
        return {
            "lista": lista,
            "tendencias": rv.tendencias(self.partidas.todas_mis_partidas(), set(self.cuentas), self.datos.nombre, hora),
            "muertes": rv.mapa_muertes(self.una(f["id"]) for f in lista),
        }

    def una(self, id_: str) -> Revision | None:
        rev: Revision | None = self.cache.kv_get(f"revision:{id_}")
        return rev
