"""Recolector de duelos: partidas de Master+ con línea de tiempo en las que sale tu campeón en tu rol.

Corea, Norteamérica y Asia-Pacífico tienen cuota propia (Riot cuenta cada host aparte), así que no le
quitan nada al panel de tu partida. EUW comparte cuota con el panel: solo se usa con el cliente quieto
y empieza por tus propias partidas (para comparar tus números con los de Master+).

Uso suelto (sin la app): py -m deepprep.recolector [--minutos 60] [--sin-europa]
"""

import logging
import msvcrt
import random
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Collection, Iterable
from typing import IO

from . import analisis as an
from . import config
from . import duelos as du
from .base_duelos import BaseDuelos
from .constantes import DURACION_MINIMA_S, SOLO_DUO
from .riot import ClaveInvalida, Cliente, ErrorRiot
from .tipos import Cancelada, Json, Partida

logger = logging.getLogger(__name__)

RUTA_CERROJO = config.DATOS / "recolector.lock"
NIVEL_LIGA = {"challengerleagues": "CHALLENGER", "grandmasterleagues": "GRANDMASTER", "masterleagues": "MASTER"}
# (plataforma, región) con su propia cuota. EUW va aparte: comparte cuota con el panel.
TODAS = [("euw1", "europe"), ("kr", "asia"), ("na1", "americas"), ("vn2", "sea")]
REGIONES = [r for r in TODAS if r[1] != "europe"]  # las de fuera, para quien juega en EUW
LIGAS = ("challengerleagues", "grandmasterleagues", "masterleagues")
DIAS = 45  # solo partidas recientes: el juego cambia con los parches
PARTIDAS_SEMILLA = 4  # de cada jugador cualquiera se miran pocas; de uno que juega tu campeón, todas


class Recolector:
    """Un hilo por región. 'pool' y 'puede_europa' son funciones: se consultan en cada vuelta."""

    def __init__(
        self,
        base: BaseDuelos,
        leer_clave: Callable[[], str],
        legendarios: Collection[int],
        pool: Callable[[], list[tuple[int, str]]],
        mis_partidas: Callable[[], list[Partida]] = list,
        mis_puuids: Callable[[], set[str]] = lambda: set(),
        cliente_europa: Cliente | None = None,
        puede_europa: Callable[[], bool] = lambda: False,
        regiones: Iterable[tuple[str, str]] = REGIONES,
        referencias: Callable[[], list[Json]] = list,
    ) -> None:
        self.base = base
        self.legendarios = legendarios
        self.pool = pool
        self.mis_partidas = mis_partidas
        self.mis_puuids = mis_puuids
        self.puede_europa = puede_europa
        self.referencias = referencias  # [{'puuid', 'region', 'campeon'}]: jugadores con los que te comparas
        cfg = config.cargar()
        self.clientes = [Cliente(dict(cfg, plataforma=p, region=r), leer_clave) for p, r in regiones]
        self.cliente_europa = cliente_europa
        self.parar = threading.Event()
        self.estado: Json = {"nuevas": 0, "error": ""}
        self._cerrojo: IO[str] | None = None

    # --- arranque: solo un recolector a la vez (la app o el suelto) --------------------------------
    def arrancar(self) -> bool:
        cerrojo: IO[str] | None = None
        try:
            cerrojo = open(RUTA_CERROJO, "w")  # noqa: SIM115  se queda abierto y cogido mientras viva el recolector
            msvcrt.locking(cerrojo.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            if cerrojo:
                cerrojo.close()
            logger.info("Ya hay otro recolector en marcha; este no arranca")
            return False
        self._cerrojo = cerrojo
        for c in self.clientes:
            threading.Thread(target=self._bucle, args=(c, False), name=f"recolector-{c.region}", daemon=True).start()
        if self.cliente_europa:
            threading.Thread(target=self._bucle, args=(self.cliente_europa, True), name="recolector-europe", daemon=True).start()
        return True

    def _bucle(self, cliente: Cliente, europa: bool) -> None:
        while not self.parar.is_set():
            try:
                if europa:
                    if not self.puede_europa():
                        self.parar.wait(30)
                        continue
                    self._mias(cliente)
                self._vuelta(cliente, europa)
            except ClaveInvalida as e:
                self.estado["error"] = str(e)
                self.parar.wait(300)
            except ErrorRiot as e:
                logger.warning("Recolector %s: %s", cliente.region, e)
                self.parar.wait(30)
            except Exception as e:  # un fallo raro no debe parar la recogida para siempre
                logger.exception("Recolector %s: %r", cliente.region, e)
                self.parar.wait(60)

    def _cancelada(self, europa: bool) -> Cancelada | None:
        """En EUW, lo que pide el recolector se deja a medias en cuanto el panel necesita la cuota."""
        return (lambda: not self.puede_europa()) if europa else None

    # --- tus partidas (EUW) -----------------------------------------------------------------------------
    def _mias(self, cliente: Cliente) -> None:
        """Línea de tiempo de tus clasificatorias con los campeones de tu pool, para tus números."""
        pool = set(self.pool())
        puuids = self.mis_puuids()
        for m in self.mis_partidas():
            if self.parar.is_set() or not self.puede_europa():
                return
            if m.get("remake") or self.base.vista(m["id"]):
                continue
            yo = next((j for j in m["jug"] if j["puuid"] in puuids), None)
            if not yo or (yo["campeon"], yo["pos"]) not in pool:
                continue
            self._bajar(cliente, m["id"], True, europa=True)

    # --- partidas de Master+ ---------------------------------------------------------------------------
    def _semillas(self, cliente: Cliente, europa: bool) -> list[str]:
        """Jugadores de Master+ de la plataforma; de paso se apunta el nivel de cada uno (para compararte con Challenger)."""
        clave = f"ligas:{cliente.plataforma}"
        ligas: dict[str, str] | None = self.base.kv_get(clave, max_edad=86400)
        if not ligas:
            ligas = {}
            for liga in LIGAS:
                datos = cliente.liga_de_elite(liga, fondo=europa, cancelada=self._cancelada(europa)) or {}
                ligas.update({e["puuid"]: NIVEL_LIGA[liga] for e in datos.get("entries", []) if e.get("puuid")})
            self.base.kv_set(clave, ligas)
        return list(ligas)

    def _referencias(self, cliente: Cliente, europa: bool) -> None:
        """Partidas recientes de tus jugadores de referencia que juegan en esta región (cada 6 horas)."""
        region = cliente.region.split(".")[0]
        desde = int(time.time()) - DIAS * 86400
        for ref in self.referencias():
            if ref["region"] != region or self.base.kv_get(f"ref_al_dia:{ref['puuid']}", max_edad=6 * 3600):
                continue
            ids = cliente.ids_partidas(ref["puuid"], cola=SOLO_DUO, n=100, desde=desde, fondo=europa) or []
            for id_ in ids:
                if self.parar.is_set() or (europa and not self.puede_europa()):
                    return
                if self.base.vista(id_):
                    continue
                m = cliente.partida(id_, fondo=europa, cancelada=self._cancelada(europa))
                suyo = next((p for p in (m or {}).get("info", {}).get("participants", []) if p["puuid"] == ref["puuid"]), None)
                # campeon None: perfil de base, valen todas sus partidas.
                otro = ref["campeon"] is not None and suyo and suyo["championId"] != ref["campeon"]
                if m is None or not suyo or otro or m["info"].get("gameDuration", 0) < DURACION_MINIMA_S:
                    self.base.marcar(id_, False)
                    continue
                self._bajar(cliente, id_, False, europa, partida=m)
            self.base.kv_set(f"ref_al_dia:{ref['puuid']}", len(ids))

    def _vuelta(self, cliente: Cliente, europa: bool) -> None:
        """Recorre jugadores de Master+; cuando sale alguien con un campeón de tu pool, sigue su historial."""
        semillas = self._semillas(cliente, europa)
        random.shuffle(semillas)
        seguir: deque[str] = deque()  # jugadores que juegan un campeón de tu pool en su posición
        seguidos: set[str] = set()
        desde = int(time.time()) - DIAS * 86400
        while (seguir or semillas) and not self.parar.is_set():
            if europa and not self.puede_europa():
                return
            self._referencias(cliente, europa)
            pool = set(self.pool())
            if not pool:
                self.parar.wait(60)
                continue
            puuid, todas = (seguir.popleft(), True) if seguir else (semillas.pop(), False)
            ids = cliente.ids_partidas(puuid, cola=SOLO_DUO, n=20, desde=desde, fondo=europa) or []
            for id_ in ids if todas else ids[:PARTIDAS_SEMILLA]:
                if self.parar.is_set() or self.base.vista(id_):
                    continue
                m = cliente.partida(id_, fondo=europa, cancelada=self._cancelada(europa))
                if not m:
                    self.base.marcar(id_, False)
                    continue
                aciertos = [p for p in m["info"]["participants"] if (p["championId"], p.get("teamPosition")) in pool]
                if not aciertos or m["info"].get("gameDuration", 0) < DURACION_MINIMA_S:
                    self.base.marcar(id_, False)
                    continue
                self._bajar(cliente, id_, False, europa, partida=m)
                for p in aciertos:
                    if p["puuid"] not in seguidos:
                        seguidos.add(p["puuid"])
                        seguir.append(p["puuid"])

    def _bajar(self, cliente: Cliente, id_: str, mia: bool, europa: bool, partida: Json | None = None) -> None:
        partida = partida or cliente.partida(id_, fondo=europa, cancelada=self._cancelada(europa))
        linea = cliente.linea(id_, fondo=europa, cancelada=self._cancelada(europa)) if partida else None
        if not (partida and linea):
            self.base.marcar(id_, False)
            return
        try:
            registros = du.extraer(partida, linea, self.legendarios)
        except (KeyError, TypeError, IndexError) as e:
            logger.warning("Partida %s con formato inesperado: %r", id_, e)
            registros = []
        if registros:
            self.base.guardar(id_, registros)
            self.estado["nuevas"] += 1
        else:
            self.base.marcar(id_, False)


def main() -> None:
    """Recolector suelto, sin la app (p. ej. para llenar la base de noche)."""
    from .app import crear_app

    config.configurar_registro()
    minutos = float(sys.argv[sys.argv.index("--minutos") + 1]) if "--minutos" in sys.argv else None
    app = crear_app(grabar=False)
    try:
        app.comprobar_clave()
    except (ClaveInvalida, ErrorRiot) as e:
        logger.error("No puedo usar la clave: %s", e)
        return
    base = BaseDuelos()
    mias = app.mis_partidas
    rec = Recolector(
        base,
        config.leer_clave,
        app.datos.legendarios,
        pool=lambda: an.pool_de(mias(), set(app.cuentas)),
        mis_partidas=mias,
        mis_puuids=lambda: set(app.cuentas),
        cliente_europa=None if "--sin-europa" in sys.argv else app.cliente,
        puede_europa=lambda: True,
    )
    logger.info("Pool: %s", [(app.datos.nombre(c), p) for c, p in rec.pool()])
    if not rec.arrancar():
        return
    inicio = time.time()
    try:
        while minutos is None or time.time() - inicio < minutos * 60:
            time.sleep(60)
            logger.info("%s nuevas: %s", base.resumen(), rec.estado["nuevas"])
    except KeyboardInterrupt:
        pass
    rec.parar.set()


if __name__ == "__main__":
    main()
