"""Cliente de la API de Riot con control de cuota.

La clave personal/de desarrollo permite 20 peticiones por segundo y 100 cada 2 minutos
por cada host (euw1 y europe cuentan aparte). El limitador espera en vez de dejar que
Riot devuelva 429.
"""

import gzip
import http.client
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from .constantes import LIGA_COLA, SOLO_DUO
from .tipos import Cancelada, Cfg, Json

# Sin User-Agent propio, Cloudflare rechaza el de urllib con "error code: 1010".
USER_AGENT = "deep-prep/2.0"

# Plataforma de una cuenta -> región de sus partidas (match-v5).
REGION_DE = {
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "me1": "europe",
    "kr": "asia",
    "jp1": "asia",
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "oc1": "sea",
    "sg2": "sea",
    "tw2": "sea",
    "vn2": "sea",
    "th2": "sea",
    "ph2": "sea",
}


class ClaveInvalida(Exception):
    """La clave falta, está caducada o Riot no la reconoce."""


class ErrorRiot(Exception):
    pass


class Limitador:
    # Un poco por debajo del límite real para absorber desfases de reloj.
    LIMITES = ((1.0, 18), (120.0, 96))

    def __init__(self, reloj: Callable[[], float] = time.monotonic, dormir: Callable[[float], None] = time.sleep) -> None:
        # Cuánto de la ventana de 2 minutos pueden gastar las tareas de fondo. La app lo baja
        # a 0 cuando se acerca una partida, para que el panel tenga la cuota entera.
        self.tope_fondo = 40
        self._lock = threading.Lock()
        self._marcas: defaultdict[str, deque[float]] = defaultdict(deque)
        self._pausa: defaultdict[str, float] = defaultdict(float)
        self._reloj = reloj
        self._dormir = dormir

    def _espera(self, host: str, fondo: bool) -> float:
        ahora = self._reloj()
        marcas = self._marcas[host]
        while marcas and marcas[0] <= ahora - 120.0:
            marcas.popleft()
        espera = max(0.0, self._pausa[host] - ahora)
        for ventana, tope in self.LIMITES:
            if fondo and ventana > 1.0:
                tope = self.tope_fondo
                if tope <= 0:
                    espera = max(espera, 1.0)
                    continue
            dentro = [t for t in marcas if t > ahora - ventana]
            if len(dentro) >= tope:
                espera = max(espera, dentro[len(dentro) - tope] + ventana - ahora)
        return espera

    def adquirir(self, host: str, fondo: bool = False, cancelada: Cancelada | None = None) -> bool:
        """Bloquea hasta que haya hueco. Devuelve False si la tarea se canceló esperando."""
        while True:
            with self._lock:
                espera = self._espera(host, fondo)
                if espera <= 0:
                    self._marcas[host].append(self._reloj())
                    return True
            if cancelada is not None and cancelada():
                return False
            self._dormir(min(espera, 0.5))

    def sincronizar(self, host: str, cabecera: str | None) -> None:
        """Ajusta la cuenta local con la de Riot (p. ej. tras reiniciar la app)."""
        if cabecera is None:
            return
        try:
            en_servidor = {int(v): int(n) for n, v in (par.split(":") for par in cabecera.split(","))}.get(120)
        except (ValueError, AttributeError):
            return
        if en_servidor is None:
            return
        with self._lock:
            ahora = self._reloj()
            marcas = self._marcas[host]
            locales = sum(1 for t in marcas if t > ahora - 120.0)
            for _ in range(en_servidor - locales):
                marcas.append(ahora)

    def penalizar(self, host: str, segundos: float) -> None:
        with self._lock:
            self._pausa[host] = max(self._pausa[host], self._reloj() + segundos)

    def estado(self, host: str) -> dict[str, float]:
        with self._lock:
            ahora = self._reloj()
            usadas = sum(1 for t in self._marcas[host] if t > ahora - 120.0)
            return {"usadas": usadas, "tope": self.LIMITES[1][1], "espera": round(self._espera(host, False), 1)}


class Cliente:
    def __init__(self, cfg: Cfg, leer_clave: Callable[[], str], limitador: Limitador | None = None) -> None:
        self.plataforma = f"{cfg['plataforma']}.api.riotgames.com"
        self.region = f"{cfg['region']}.api.riotgames.com"
        self._leer_clave = leer_clave
        self.limitador = limitador or Limitador()
        self.peticiones = 0

    def _get(self, host: str, ruta: str, fondo: bool = False, cancelada: Cancelada | None = None) -> Any:
        """El JSON de la respuesta, o None si es un 404 o si la tarea se cancela esperando cuota."""
        clave = self._leer_clave()
        if not clave:
            raise ClaveInvalida(
                "Falta tu clave de la API de Riot. Entra en developer.riotgames.com con tu cuenta del LoL, "
                "copia la clave y pégala aquí."
            )
        url = f"https://{host}{ruta}"
        for intento in range(4):
            if not self.limitador.adquirir(host, fondo, cancelada):
                return None
            pet = urllib.request.Request(
                url, headers={"X-Riot-Token": clave, "User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
            )
            self.peticiones += 1
            try:
                with urllib.request.urlopen(pet, timeout=20) as resp:
                    cuerpo = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        cuerpo = gzip.decompress(cuerpo)
                    self.limitador.sincronizar(host, resp.headers.get("X-App-Rate-Limit-Count"))
                    return json.loads(cuerpo)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code in (401, 403):
                    raise ClaveInvalida(f"Riot rechaza la clave ({e.code}). Suele ser que ha caducado.") from e
                if e.code == 429:
                    self.limitador.penalizar(host, float(e.headers.get("Retry-After") or 5) + 1)
                    continue
                if e.code >= 500 and intento < 3:
                    time.sleep(1.5 * (intento + 1))
                    continue
                raise ErrorRiot(f"{e.code} en {ruta}") from e
            # Una respuesta cortada a medias (IncompleteRead, o un gzip sin acabar) es un fallo de red más: se reintenta.
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, EOFError) as e:
                if intento < 3:
                    time.sleep(1.5 * (intento + 1))
                    continue
                raise ErrorRiot(f"Sin conexión con {host}: {e}") from e
        raise ErrorRiot(f"Demasiados reintentos en {ruta}")

    def poner_plataforma(self, plataforma: str, region: str) -> None:
        self.plataforma = f"{plataforma}.api.riotgames.com"
        self.region = f"{region}.api.riotgames.com"

    def comprobar(self) -> Json | None:
        """Prueba la clave sin cuenta de por medio (estado de los servidores)."""
        estado: Json | None = self._get(self.plataforma, "/lol/status/v4/platform-data")
        return estado

    # --- cuentas -------------------------------------------------------------------
    def cuenta_por_riot_id(self, nombre: str, tag: str) -> Json | None:
        """{'puuid', 'gameName', 'tagLine'} de la cuenta, o None si no existe."""
        q = urllib.parse.quote
        cuenta: Json | None = self._get(
            self.region, f"/riot/account/v1/accounts/by-riot-id/{q(nombre, safe='')}/{q(tag, safe='')}"
        )
        return cuenta

    def region_de_juego(self, puuid: str) -> Json | None:
        """En qué plataforma juega al LoL una cuenta: {'puuid', 'game', 'region': 'EUW1'}, o None."""
        region: Json | None = self._get(self.region, f"/riot/account/v1/region/by-game/lol/by-puuid/{puuid}")
        return region

    # --- partida en vivo y datos del jugador (host de plataforma) --------------------
    def partida_activa(self, puuid: str) -> Json | None:
        """La partida en vivo de esa cuenta (spectator-v5), o None si no está jugando."""
        juego: Json | None = self._get(self.plataforma, f"/lol/spectator/v5/active-games/by-summoner/{puuid}")
        return juego

    def ligas(self, puuid: str, cancelada: Cancelada | None = None) -> list[Json] | None:
        """Sus ligas (una entrada por cola clasificatoria en la que ha jugado)."""
        ligas: list[Json] | None = self._get(self.plataforma, f"/lol/league/v4/entries/by-puuid/{puuid}", cancelada=cancelada)
        return ligas

    def maestrias(self, puuid: str, cancelada: Cancelada | None = None) -> list[Json] | None:
        """Maestría de todos los campeones de la cuenta, de más a menos puntos."""
        ruta = f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
        maestrias: list[Json] | None = self._get(self.plataforma, ruta, cancelada=cancelada)
        return maestrias

    def liga_de_elite(self, liga: str, fondo: bool = False, cancelada: Cancelada | None = None) -> Json | None:
        """Los jugadores de solo/dúo de una liga de la plataforma: challengerleagues, grandmasterleagues o masterleagues."""
        jugadores: Json | None = self._get(
            self.plataforma, f"/lol/league/v4/{liga}/by-queue/{LIGA_COLA[SOLO_DUO]}", fondo, cancelada
        )
        return jugadores

    # --- historial (host regional) ---------------------------------------------------
    def ids_partidas(
        self,
        puuid: str,
        cola: int | None = None,
        tipo: str | None = None,
        inicio: int = 0,
        n: int = 20,
        desde: float | None = None,
        fondo: bool = False,
        cancelada: Cancelada | None = None,
    ) -> list[str]:
        """Ids de sus partidas, de la más reciente a la más antigua (de esa cola o tipo, y desde esa fecha en s)."""
        params: dict[str, int | str] = {"start": inicio, "count": n}
        if cola:
            params["queue"] = cola
        if tipo:
            params["type"] = tipo
        if desde:
            params["startTime"] = int(desde)
        ruta = f"/lol/match/v5/matches/by-puuid/{puuid}/ids?{urllib.parse.urlencode(params)}"
        ids: list[str] = self._get(self.region, ruta, fondo, cancelada) or []
        return ids

    def partida(self, id_: str, fondo: bool = False, cancelada: Cancelada | None = None) -> Json | None:
        """La partida entera de match-v5 (~80 KB)."""
        partida: Json | None = self._get(self.region, f"/lol/match/v5/matches/{id_}", fondo, cancelada)
        return partida

    def linea(self, id_: str, fondo: bool = False, cancelada: Cancelada | None = None) -> Json | None:
        """Su línea de tiempo de match-v5 (~850 KB)."""
        linea: Json | None = self._get(self.region, f"/lol/match/v5/matches/{id_}/timeline", fondo, cancelada)
        return linea
