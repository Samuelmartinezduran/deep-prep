"""Datos estáticos: campeones (Data Dragon) y en qué rol se juega cada uno (Meraki)."""

import json
import logging
import re
import urllib.request
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self

from . import config
from .riot import USER_AGENT

if TYPE_CHECKING:
    from .cache import Cache

logger = logging.getLogger(__name__)

URL_VERSIONES = "https://ddragon.leagueoflegends.com/api/versions.json"
URL_CAMPEONES = "https://ddragon.leagueoflegends.com/cdn/{v}/data/es_ES/champion.json"
URL_OBJETOS = "https://ddragon.leagueoflegends.com/cdn/{v}/data/es_ES/item.json"
URL_RUNAS = "https://ddragon.leagueoflegends.com/cdn/{v}/data/es_ES/runesReforged.json"
URL_ROLES = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/championrates.json"

DIA = 86400
# Imágenes de campeones y el minimapa: se bajan una vez y se guardan en disco (el overlay no espera a la red).
URL_IMAGEN = {
    "campeon": "https://ddragon.leagueoflegends.com/cdn/{v}/img/champion/{n}.png",
    "splash": "https://ddragon.leagueoflegends.com/cdn/img/champion/centered/{n}_0.jpg",
    # El minimapa no cambia con los parches; esta es la última versión que Data Dragon publicó.
    "mapa": "https://ddragon.leagueoflegends.com/cdn/6.8.1/img/map/{n}.png",
}
EXT_IMAGEN = {"campeon": ".png", "splash": ".jpg", "mapa": ".png"}
RUTA_IMAGENES = config.DATOS / "imagenes"
NOMBRE_SEGURO = re.compile(r"^[A-Za-z0-9]+$")


def imagen(tipo: str, clave: str, version: str) -> bytes | None:
    """Bytes de la imagen (de disco o recién bajada), o None (sin red, o un tipo o una clave que no valen).

    tipo: una clave de URL_IMAGEN; clave: el nombre del campeón (o del mapa) en Data Dragon; version: el parche
    (solo cuenta para los retratos, que cambian con él).
    """
    if tipo not in URL_IMAGEN or not NOMBRE_SEGURO.match(clave):
        return None
    destino = RUTA_IMAGENES / tipo / (version if tipo == "campeon" else "") / (clave + EXT_IMAGEN[tipo])
    if destino.is_file():
        return destino.read_bytes()
    try:
        pet = urllib.request.Request(URL_IMAGEN[tipo].format(v=version, n=clave), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(pet, timeout=10) as r:
            datos: bytes = r.read()
    except OSError:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    return datos


def _descargar(url: str) -> Any:
    pet = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(pet, timeout=20) as resp:
        return json.loads(resp.read())


class Datos:
    def __init__(self, cache: "Cache | None") -> None:
        """Carga los datos de la caché o, si son viejos, de Data Dragon. Sin caché (None) empieza vacío y no baja nada."""
        self.version = ""
        self.campeones: dict[int, dict[str, str]] = {}  # id -> {"nombre", "clave"}
        self.roles: dict[int, dict[str, float]] = {}  # id -> {posición: frecuencia relativa}
        self.objetos: dict[int, str] = {}  # id -> nombre
        self.legendarios: set[int] = set()  # ids de objetos completos (los que cuentan como "primer objeto")
        self.runas: dict[int, str] = {}  # id de runa o de rama -> nombre
        if cache is not None:
            self._cargar(cache)

    @classmethod
    def fijos(cls, version: str, campeones: Mapping[int, Mapping[str, str]]) -> Self:
        """Datos ya sabidos, sin caché ni red (los de la demo): la versión de Data Dragon y los campeones."""
        datos = cls(None)
        datos.version = version
        datos.campeones = {int(k): dict(v) for k, v in campeones.items()}
        return datos

    def _cargar(self, cache: "Cache") -> None:
        guardado = cache.kv_get("ddragon", max_edad=DIA / 2)
        if not guardado or "objetos" not in guardado:
            try:
                version = _descargar(URL_VERSIONES)[0]
                datos = _descargar(URL_CAMPEONES.format(v=version))["data"]
                objetos = _descargar(URL_OBJETOS.format(v=version))["data"]
                runas: dict[int, str] = {}
                for rama in _descargar(URL_RUNAS.format(v=version)):
                    runas[rama["id"]] = rama["name"]
                    for fila in rama["slots"]:
                        runas.update({r["id"]: r["name"] for r in fila["runes"]})
                guardado = {
                    "version": version,
                    "campeones": {c["key"]: {"nombre": c["name"], "clave": c["id"]} for c in datos.values()},
                    "objetos": {k: o["name"] for k, o in objetos.items()},
                    # Completos: caros, sin mejora posterior, de la Grieta y que no son botas.
                    "legendarios": [
                        int(k)
                        for k, o in objetos.items()
                        if o["gold"]["total"] >= 2200
                        and o["gold"].get("purchasable", True)
                        and not o.get("into")
                        and o.get("maps", {}).get("11")
                        and "Boots" not in o.get("tags", [])
                    ],
                    "runas": runas,
                }
                cache.kv_set("ddragon", guardado)
            except (OSError, ValueError, KeyError, IndexError) as e:
                # Sin red se sigue con lo último que hubiera, aunque esté viejo.
                guardado = cache.kv_get("ddragon") or {"version": "", "campeones": {}}
                logger.warning("Data Dragon no responde (%s); uso los datos guardados", e)
        self.version = guardado["version"]
        self.campeones = {int(k): v for k, v in guardado["campeones"].items()}
        self.objetos = {int(k): v for k, v in guardado.get("objetos", {}).items()}
        self.legendarios = set(guardado.get("legendarios", []))
        self.runas = {int(k): v for k, v in guardado.get("runas", {}).items()}

        roles = cache.kv_get("roles", max_edad=7 * DIA)
        if roles is None:
            try:
                roles = {k: {pos: d.get("playRate", 0) for pos, d in v.items()} for k, v in _descargar(URL_ROLES)["data"].items()}
                cache.kv_set("roles", roles)
            except (OSError, ValueError, KeyError) as e:
                roles = cache.kv_get("roles") or {}
                logger.warning("No hay datos de roles por campeón (%s); los roles saldrán del historial", e)
        self.roles = {int(k): v for k, v in roles.items()}

    def nombre(self, id_: int) -> str:
        return self.campeones.get(id_, {}).get("nombre", f"Campeón {id_}")

    def objeto(self, id_: int) -> str:
        return self.objetos.get(id_, f"Objeto {id_}")

    def runa(self, id_: int) -> str:
        return self.runas.get(id_, f"Runa {id_}")

    def icono(self, id_: int) -> str:
        # Lo sirve el servidor local desde disco (lo baja de Data Dragon la primera vez).
        c = self.campeones.get(id_)
        return f"/ddragon/campeon/{c['clave']}.png" if c and self.version else ""

    def splash(self, id_: int) -> str:
        c = self.campeones.get(id_)
        return f"/ddragon/splash/{c['clave']}.jpg" if c else ""
