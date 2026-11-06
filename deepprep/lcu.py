"""Lectura de la API local del cliente del LoL (solo consultas, nunca escribe ni automatiza nada).

El cliente deja en su carpeta un 'lockfile' con el puerto y la contraseña de esa sesión.
Con eso se sabe qué cuenta está abierta y en qué fase está (cola, selección, partida).
"""

import base64
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Región del cliente -> plataforma de la API de Riot.
PLATAFORMA_DE = {
    "EUW": "euw1",
    "EUNE": "eun1",
    "NA": "na1",
    "KR": "kr",
    "BR": "br1",
    "LAN": "la1",
    "LAS": "la2",
    "OCE": "oc1",
    "TR": "tr1",
    "RU": "ru",
    "JP": "jp1",
    "ME": "me1",
    "PH": "ph2",
    "SG": "sg2",
    "TH": "th2",
    "TW": "tw2",
    "VN": "vn2",
}
AJUSTES_RIOT = (
    Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    / "Riot Games/Metadata/league_of_legends.live/league_of_legends.live.product_settings.yaml"
)


def rutas_posibles(configurada: str | Path) -> Iterator[Path]:
    """Dónde puede estar instalado el LoL: la ruta configurada, la que apunta el propio Riot y las habituales."""
    yield Path(configurada)
    try:
        m = re.search(r'product_install_full_path:\s*"?([^"\r\n]+)"?', AJUSTES_RIOT.read_text(encoding="utf-8", errors="replace"))
        if m:
            yield Path(m.group(1).strip())
    except OSError:
        pass
    for disco in "CDEFG":
        yield Path(f"{disco}:/Riot Games/League of Legends")
    yield Path("C:/Program Files/Riot Games/League of Legends")


# Posición asignada en la selección (solo en colas con roles) -> posición de Riot en las partidas.
POS_SELECCION = {"top": "TOP", "jungle": "JUNGLE", "middle": "MIDDLE", "bottom": "BOTTOM", "utility": "UTILITY"}


class Cliente:
    def __init__(self, ruta_lol: str | Path) -> None:
        self._configurada = ruta_lol
        self.ruta = Path(ruta_lol)  # carpeta del LoL (se corrige sola si está en otro sitio)
        self._buscada = 0.0
        # El cliente usa un certificado propio; la conexión no sale de 127.0.0.1.
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE

    def _conexion(self) -> tuple[str, str] | None:
        try:
            partes = (self.ruta / "lockfile").read_text(encoding="utf-8").strip().split(":")
        except OSError:
            # El lockfile solo existe con el cliente abierto: si no está, se mira (sin prisa) si el LoL está en otro sitio.
            if time.time() - self._buscada > 30:
                self._buscada = time.time()
                for ruta in rutas_posibles(self._configurada):
                    if (ruta / "lockfile").is_file():
                        self.ruta = ruta
                        return self._conexion()
                    if not (self.ruta / "Config").is_dir() and (ruta / "Config").is_dir():
                        self.ruta = ruta  # instalado ahí aunque el cliente esté cerrado (para leer game.cfg)
            return None
        if len(partes) < 5:
            return None
        return partes[2], partes[3]

    def get(self, ruta: str) -> Any:
        """Devuelve el JSON de la ruta, o None si el cliente no está abierto o no responde."""
        con = self._conexion()
        if not con:
            return None
        puerto, clave = con
        cred = base64.b64encode(f"riot:{clave}".encode()).decode()
        pet = urllib.request.Request(f"https://127.0.0.1:{puerto}{ruta}", headers={"Authorization": f"Basic {cred}"})
        try:
            with urllib.request.urlopen(pet, timeout=3, context=self._ssl) as resp:
                return json.loads(resp.read() or b"null")
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def estado(self) -> dict[str, str] | None:
        """{'fase', 'nombre', 'tag'} o None si el cliente está cerrado."""
        fase = self.get("/lol-gameflow/v1/gameflow-phase")
        if not isinstance(fase, str):
            return None
        yo = self.get("/lol-summoner/v1/current-summoner") or {}
        return {"fase": fase, "nombre": yo.get("gameName", ""), "tag": yo.get("tagLine", "")}

    def plataforma(self) -> str | None:
        """Plataforma de la API (euw1, na1…) según la región del cliente, o None."""
        r = self.get("/riotclient/region-locale")
        return PLATAFORMA_DE.get(str((r or {}).get("region", "")).upper()) if isinstance(r, dict) else None

    def reloj(self) -> float | None:
        """Segundos de partida según la API local del propio juego (puerto 2999), o None si aún no responde.

        Solo sirve para distinguir la pantalla de carga del juego ya empezado y para el reloj del panel:
        de esta API no se saca ningún dato en vivo para enseñarlo.
        """
        try:
            with urllib.request.urlopen("https://127.0.0.1:2999/liveclientdata/gamestats", timeout=1, context=self._ssl) as resp:
                datos = json.loads(resp.read() or b"null")
        except (urllib.error.URLError, OSError, ValueError):
            return None
        t = datos.get("gameTime") if isinstance(datos, dict) else None
        return float(t) if isinstance(t, (int, float)) else None

    def mapa(self) -> int:
        """Id del mapa de la partida en curso (11 = Grieta del Invocador), o 0 si no se sabe."""
        flujo = self.get("/lol-gameflow/v1/session")
        if not isinstance(flujo, dict):
            return 0
        return (flujo.get("map") or {}).get("id") or ((flujo.get("gameData") or {}).get("queue") or {}).get("mapId") or 0

    def seleccion(self) -> dict[str, Any] | None:
        """Selección en curso: {'mio', 'aliados', 'rivales'} con ids de campeón (0 = sin elegir) y 'cola'."""
        s = self.get("/lol-champ-select/v1/session")
        if not isinstance(s, dict) or "myTeam" not in s:
            return None
        celda = s.get("localPlayerCellId")
        mio = 0
        pos = ""
        aliados: list[int] = []
        for j in s.get("myTeam", []):
            campeon = j.get("championId") or j.get("championPickIntent") or 0
            if j.get("cellId") == celda:
                mio = campeon
                pos = POS_SELECCION.get(j.get("assignedPosition") or "", "")
            elif campeon:
                aliados.append(campeon)
        rivales = [j["championId"] for j in s.get("theirTeam", []) if j.get("championId")]
        flujo = self.get("/lol-gameflow/v1/session")
        cola = ((flujo.get("gameData") or {}).get("queue") or {}).get("id", 0) if isinstance(flujo, dict) else 0
        return {"mio": mio, "aliados": aliados, "rivales": rivales, "cola": cola, "pos": pos}
