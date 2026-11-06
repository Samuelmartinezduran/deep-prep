"""Quita de los datos de prueba y de las maquetas todo lo que identifica a un jugador real.

Las pruebas y las maquetas salen de partidas reales. Antes de guardarlas en el repositorio se cambian
los Riot ID, los PUUID, los id de invocador y los id de partida por valores inventados, siempre los
mismos para el mismo jugador, para que las partidas sigan cuadrando entre sí (la partida y su línea
de tiempo, el panel y la revisión). Lo demás (campeones, objetos, oro, posiciones) no identifica a
nadie y se queda como está.

Uso: py herramientas/anonimizar.py ARCHIVO [ARCHIVO ...]   (.json o .json.gz; se reescriben en su sitio)
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

ETIQUETA = "DEMO"
NOMBRES = [
    "Kestrel", "Nightjar", "Mossback", "Lanternfish", "Quillon", "Sablewing", "Driftmark", "Brindle",
    "Tallow", "Corvid", "Ashgrove", "Saltmarsh", "Halcyon", "Fennec", "Ironbark", "Gloam", "Vesper",
    "Larkspur", "Thistle", "Kelpie", "Mistral", "Orrery", "Petrichor", "Starling", "Wrenfield",
    "Bramble", "Cinderowl", "Rookseven", "Marrow", "Pinefall",
]
CLAVES_PUUID = {"puuid"}
CLAVES_INVOCADOR = {"summonerId", "accountId"}
CLAVES_PARTIDA = {"gameId", "matchId", "id"}


class Anonimizador:
    """Guarda las sustituciones para que un mismo jugador o partida reciba siempre el mismo valor falso."""

    def __init__(self) -> None:
        self.nombres: dict[str, str] = {}
        self.puuids: dict[str, str] = {}
        self.invocadores: dict[str, str] = {}
        self.partidas: dict[str, str] = {}

    def nombre(self, real: str) -> str:
        if real not in self.nombres:
            self.nombres[real] = NOMBRES[len(self.nombres) % len(NOMBRES)] + (
                "" if len(self.nombres) < len(NOMBRES) else str(len(self.nombres) // len(NOMBRES)))
        return self.nombres[real]

    def puuid(self, real: str) -> str:
        return self.puuids.setdefault(real, f"puuid-demo-{len(self.puuids) + 1:02d}")

    def invocador(self, real: str) -> str:
        return self.invocadores.setdefault(real, f"invocador-demo-{len(self.invocadores) + 1:02d}")

    def partida(self, real: str) -> str:
        return self.partidas.setdefault(real, str(7_000_000_001 + len(self.partidas)))

    # --- recorrido -------------------------------------------------------------------------------

    def recoger(self, x: Any) -> None:
        """Primer pase: apunta a cada jugador con su nombre para darle un nombre falso estable."""
        if isinstance(x, dict):
            if "riotId" in x and isinstance(x["riotId"], str) and "#" in x["riotId"]:
                self.nombre(x["riotId"].split("#")[0])
            if isinstance(x.get("riotIdGameName"), str) and x["riotIdGameName"]:
                self.nombre(x["riotIdGameName"])
            if "tag" in x and isinstance(x.get("nombre"), str):  # jugador de la maqueta del panel
                self.nombre(x["nombre"])
            if isinstance(x.get("cuenta"), str) and "#" in x["cuenta"]:
                self.nombre(x["cuenta"].split("#")[0])
            for v in x.values():
                self.recoger(v)
        elif isinstance(x, list):
            for v in x:
                self.recoger(v)

    def cambiar(self, x: Any, clave: str | None = None, padre: dict | None = None) -> Any:
        if isinstance(x, dict):
            return {k: self.cambiar(v, k, x) for k, v in x.items()}
        if isinstance(x, list):
            return [self.cambiar(v, clave, padre) for v in x]
        if isinstance(x, bool) or x is None:
            return x
        if clave in CLAVES_PUUID and isinstance(x, str):
            return self.puuid(x)
        if clave in CLAVES_INVOCADOR and isinstance(x, str) and x:
            return self.invocador(x)
        if clave in CLAVES_PARTIDA and self._es_id_partida(x):
            return self._partida_misma_forma(x)
        if clave in {"riotIdTagline", "tag", "tagLine"} and isinstance(x, str) and x:
            return ETIQUETA
        if isinstance(x, str):
            return self._texto(x)
        return x

    @staticmethod
    def _es_id_partida(x: Any) -> bool:
        s = str(x)
        numero = s.split("_", 1)[1] if "_" in s else s
        return numero.isdigit() and len(numero) >= 9

    def _partida_misma_forma(self, x: Any) -> Any:
        s = str(x)
        prefijo, _, numero = s.rpartition("_")
        falso = self.partida(numero)
        nuevo = f"{prefijo}_{falso}" if prefijo else falso
        return int(nuevo) if isinstance(x, int) else nuevo

    def _texto(self, s: str) -> str:
        """Cualquier otro texto: nombres reales (solos o como Nombre#TAG), PUUID e id de partida sueltos."""
        if s in self.puuids:
            return self.puuids[s]
        nombre, almohadilla, _ = s.partition("#")
        if almohadilla and nombre in self.nombres:
            return f"{self.nombres[nombre]}#{ETIQUETA}"
        if s in self.nombres:
            return self.nombres[s]
        for real, falso in self.partidas.items():
            s = s.replace(real, falso)
        return s


def _leer(ruta: Path) -> Any:
    datos = gzip.decompress(ruta.read_bytes()) if ruta.suffix == ".gz" else ruta.read_bytes()
    return json.loads(datos)


def _escribir(ruta: Path, datos: Any) -> None:
    if ruta.suffix == ".gz":
        ruta.write_bytes(gzip.compress(json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
    else:
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def anonimizar(rutas: list[Path], anon: Anonimizador | None = None) -> Anonimizador:
    """Anonimiza varios archivos con las mismas sustituciones (una partida y su línea de tiempo cuadran)."""
    anon = anon or Anonimizador()
    contenidos = [_leer(r) for r in rutas]
    for c in contenidos:
        anon.recoger(c)
    for c in contenidos:  # los id de partida y PUUID se apuntan antes de tocar textos sueltos
        anon.cambiar(c)
    for ruta, c in zip(rutas, contenidos):
        _escribir(ruta, anon.cambiar(c))
    return anon


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    hecho = anonimizar([Path(a) for a in sys.argv[1:]])
    print(f"{len(hecho.nombres)} jugadores, {len(hecho.puuids)} PUUID y {len(hecho.partidas)} partidas cambiados")
