"""Modo demo: la app con una partida de ejemplo, sin el LoL, sin clave de Riot y sin tocar tus datos.

py -m deepprep --demo (o DeepPrep.exe --demo) abre la ventana de siempre con AppDemo en vez de la app de verdad.
La barra de arriba del panel (web/js/demo.js) cambia de escena: selección de campeón, pantalla de carga, en partida,
revisiones y ajustes. No hay vigía del cliente del LoL, grabación, recolector, actualizaciones, accesos directos ni
arranque con Windows, y ninguna llamada a la API de Riot; solo las imágenes de los campeones salen de Data Dragon
(sin red, el panel funciona igual, sin ellas). Lo que se guarda va a una carpeta temporal nueva (config.carpeta_demo)
que se borra al salir.

Los datos de ejemplo van en esta carpeta, en JSON, y no son de nadie: todos los jugadores son Nombre#DEMO.
- panel.json (pantalla de carga y en partida) y seleccion.json: salen de herramientas/maquetas/partida.json, con los
  rangos, las maestrías y las rachas cambiados; el mapa del jungla rival y el duelo están inventados.
- partida.json y linea.json: la partida de tests/datos, ya reducida. Las revisiones salen de ahí con el mismo código
  que las de verdad (revision.revisar); revisiones.json dice cuáles hay, sus LP, lo que preveía el panel y la
  comparación con tu referencia, y trae tus tendencias de la temporada (inventadas).
- ajustes.json: la configuración con la que empieza (cuentas, reglas, notas y referencias) y las partidas guardadas
  de cada jugador de referencia.
- campeones.json: nombre y clave de cada campeón en Data Dragon, para no pedirlos a la red.
"""

import copy
import json
import logging
import shutil
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .. import config
from .. import revision as rv
from ..actualizador import Actualizador
from ..ajustes import Ajustes
from ..app import para_el_modo, sin_arranque_windows
from ..ddragon import Datos
from ..revisiones import CLAVES_INDICE
from ..riot import Limitador
from ..servidor import Accion
from ..tipos import Cfg, EstadoVersion, Json, Panel, Resultado, Revision
from ..vigia import FASES

logger = logging.getLogger(__name__)

DATOS_DEMO = Path(__file__).resolve().parent
# Escenas de la partida de ejemplo. Revisiones y Ajustes son pestañas del panel: las abre la barra, sin pasar por aquí.
ESCENAS = ("seleccion", "carga", "juego")
ESCENA_INICIAL = "carga"
FASE = {"seleccion": "ChampSelect", "carga": "InProgress", "juego": "InProgress"}
MODO = {"seleccion": "previa", "carga": "carga", "juego": "juego"}
# Reloj del juego en la escena «En partida» (segundos); a partir de ahí lo hace avanzar el panel.
RELOJ = 14 * 60 + 5.0
CUENTA = "Driftmark#DEMO"
SIN_GRABACIONES = "Sin grabaciones en la demo"


def leer(nombre: str) -> Any:
    """Uno de los JSON de la demo (de esta carpeta)."""
    return json.loads((DATOS_DEMO / nombre).read_text(encoding="utf-8"))


def borrar_carpeta(carpeta: Path, intentos: int = 10) -> bool:
    """Borra la carpeta de datos de la demo al salir. Solo una de config.carpeta_demo(): nunca otra.

    Devuelve si ya no está. Windows puede tener algo abierto un momento (el antivirus): se reintenta un poco.
    """
    if not config.es_carpeta_demo(carpeta):
        logger.warning("No borro %s: no es una carpeta de la demo", carpeta)
        return False
    for _ in range(intentos):
        shutil.rmtree(carpeta, ignore_errors=True)
        if not carpeta.exists():
            return True
        time.sleep(0.2)
    return False


class SinActualizaciones(Actualizador):
    """La demo no busca versiones nuevas ni apunta qué novedades has visto."""

    def __init__(self) -> None:
        super().__init__(None)

    def arrancar(self) -> None:
        pass

    def novedades(self) -> Json | None:
        return None

    def novedades_vistas(self) -> Resultado:
        return {"ok": True}


class ReferenciasDemo:
    """Tus jugadores de referencia sin preguntar a Riot: vale cualquier Nombre#TAG.

    partidas: partidas guardadas de cada jugador ('nombre#tag' en minúsculas); los que no están, sin dato.
    """

    def __init__(self, cfg: Cfg, partidas: Mapping[str, int]) -> None:
        self.cfg = cfg
        self.partidas = partidas

    def resolver_referencia(self, rid: str) -> str:
        nombre, _, tag = rid.partition("#")
        return "" if nombre.strip() and tag.strip() else f"{rid}: las referencias van como Nombre#TAG."

    def partidas_de_referencias(self) -> tuple[dict[str, int | None], int | None]:
        referencias: dict[str, str] = self.cfg.get("referencias") or {}
        perfil: str = self.cfg.get("perfil_base") or ""
        por_campeon = {campeon: self.partidas.get(rid.lower()) for campeon, rid in referencias.items()}
        return por_campeon, self.partidas.get(perfil.lower()) if perfil else None


class AppDemo:
    """Lo mismo que app.App para el servidor y las ventanas (tipos.AppDelPanel), con la partida de ejemplo.

    carpeta: donde va lo que se guarda desde Ajustes (la temporal de la demo). Las herramientas pueden cambiar el panel
    de ejemplo por otro (panel), enseñar unas novedades o una versión nueva lista (novedades, version) y fijar la hora
    de las revisiones (ahora, en segundos).
    """

    def __init__(
        self,
        carpeta: Path,
        *,
        escena: str = ESCENA_INICIAL,
        panel: Panel | None = None,
        novedades: Json | None = None,
        version: EstadoVersion | None = None,
        ahora: float | None = None,
    ) -> None:
        self.carpeta = carpeta
        campeones = leer("campeones.json")
        self.datos = Datos.fijos(
            campeones["version"], {int(k): {"nombre": n, "clave": c} for k, (n, c) in campeones["campeones"].items()}
        )
        self._por_nombre = {c["nombre"]: i for i, c in self.datos.campeones.items()}
        ajustes = leer("ajustes.json")
        self.cfg: Cfg = copy.deepcopy(config.POR_DEFECTO) | ajustes["config"]
        self.configuracion = config.Configuracion(self.cfg, self._guardar)
        self.actualizador = SinActualizaciones()
        if version:
            self.actualizador.estado = version
        self._ajustes = Ajustes(
            self.configuracion,
            self.datos,
            ReferenciasDemo(self.cfg, ajustes["partidas_de"]),
            self.actualizador,
            sin_arranque_windows,
            lambda nuevo: None,  # el panel lee las notas y las reglas de la configuración cada vez
        )
        self.escena = escena if escena in ESCENAS else ESCENA_INICIAL
        self._panel: Panel = panel or leer("panel.json")
        self._seleccion: Json = leer("seleccion.json")
        self._novedades = novedades
        revisiones = leer("revisiones.json")
        self._tendencias: Json = revisiones["tendencias"]
        self._revisiones = self._preparar_revisiones(revisiones["revisiones"], time.time() if ahora is None else ahora)
        self.ultima_consulta = time.time()  # última vez que el panel pidió el estado
        self.al_mostrar: Callable[[], None] | None = None
        self.al_salir: Callable[[], None] | None = None
        self.ventana_visible: Callable[[], bool] | None = None

    def _guardar(self, valores: Cfg) -> None:
        config.escribir_atomico(self.carpeta / "config.json", json.dumps(valores, ensure_ascii=False, indent=2))

    def _preparar_revisiones(self, ejemplos: list[Json], ahora: float) -> dict[str, Revision]:
        """Las revisiones de ejemplo, de la partida de partida.json vista por cada jugador y fechadas hace un rato."""
        partida, linea = leer("partida.json"), leer("linea.json")
        revisiones: dict[str, Revision] = {}
        for ej in ejemplos:
            empieza = int((ahora - ej["hace_min"] * 60) * 1000)
            rev = rv.revisar(
                dict(partida, id=ej["id"], creacion=empieza), linea, ej["puuid"], self.datos.nombre, ej["panel"], ej["desfase"]
            )
            if not rev:
                continue
            for i, m in enumerate(rev["muertes"]):
                m["clip"] = f"clip_{i + 1:02d}.mp4"
            rev.update(referencia=ej["referencia"], lp=ej["lp"], carpeta="demo", icono=self.datos.icono(rev["campeon_id"]))
            revisiones[rev["id"]] = rev
        return revisiones

    # --- lo que lee el servidor -------------------------------------------------------------------
    @property
    def fase(self) -> str | None:
        return FASE[self.escena]

    @property
    def modo(self) -> str:
        return MODO[self.escena]

    def rutas(self) -> dict[str, Accion]:
        """Lo que la demo añade a la API del panel: cambiar de escena desde la barra."""
        return {"/api/demo": lambda app, cuerpo: self.elegir_escena(str(cuerpo.get("escena", "")))}

    def elegir_escena(self, escena: str) -> Resultado:
        if escena not in ESCENAS:
            return {"ok": False, "error": "Esa escena no existe."}
        self.escena = escena
        return {"ok": True}

    def panel(self) -> Panel:
        """El panel de la partida de ejemplo con tus notas y tus reglas de ahora (las de Ajustes)."""
        equipos = self._panel["equipos"]
        rivales = [self._por_nombre.get(f["campeon"], 0) for f in equipos["rival"]]
        todos = [self._por_nombre.get(f["campeon"], 0) for f in equipos["aliado"]] + rivales
        return dict(
            self._panel,
            notas=self._ajustes.notas_de(todos, set(rivales)),
            recordatorios=list(self.cfg.get("recordatorios") or []),
        )

    def seleccion(self) -> Json:
        """La selección de campeón de ejemplo (el rival aún no lo ha elegido todo) con tus notas de ahora."""
        rivales = [f["campeon"] for f in self._seleccion["historial"]["vs"]]
        mio = self._por_nombre.get(self._seleccion["mio"]["nombre"], 0)
        return dict(self._seleccion, notas=self._ajustes.notas_de([mio, *rivales], set(rivales)))

    def estado(self, contar: bool = True) -> Json:
        if contar:  # el overlay no cuenta como mirar el panel
            self.ultima_consulta = time.time()
        fase = FASE[self.escena]
        en_seleccion = self.escena == "seleccion"
        return {
            "fase": fase,
            "fase_txt": FASES.get(fase, fase),
            "modo": self.modo,
            "reloj": RELOJ if self.escena == "juego" else None,
            "overlay": {"activo": bool(self.cfg.get("overlay", True)), "atajo": self.cfg.get("atajo_overlay", ""), "aviso": ""},
            "cuenta": CUENTA,
            "clave": {"ok": True, "error": ""},  # sin clave de Riot, y sin el aviso de pegarla
            "cuota": {"usadas": 0, "tope": Limitador.LIMITES[1][1], "espera": 0.0},
            "sync": {"hechas": 0, "total": 0},
            "grabacion": None,
            "ultima_revision": None,
            "seleccion": self.seleccion() if en_seleccion else None,
            "recolector": None,
            "version": self.actualizador.estado,
            "novedades": self._novedades,
            # Ya jugando, lo mismo que quita la app de verdad (normas de Riot).
            "panel": None if en_seleccion else para_el_modo(self.panel(), self.modo),
            "demo": {"escena": self.escena},
        }

    def revisiones(self) -> Json:
        revisiones = sorted(self._revisiones.values(), key=lambda r: r["fecha"], reverse=True)
        lista = [dict({k: r[k] for k in CLAVES_INDICE}, lp=(r.get("lp") or {}).get("cambio")) for r in revisiones]
        return {"lista": lista, "tendencias": self._tendencias, "muertes": rv.mapa_muertes(revisiones)}

    def revision(self, id_: str) -> Revision | None:
        return self._revisiones.get(id_)

    def ajustes(self) -> Json:
        return self._ajustes.leer()

    def guardar_ajustes(self, cambios: Any) -> Resultado:
        return self._ajustes.guardar(cambios)

    # --- lo que en la demo no se hace -----------------------------------------------------------
    def buscar(self, rid: str) -> Resultado:
        return {"ok": False, "error": "La demo no busca jugadores: eso necesita la API de Riot."}

    def volver(self) -> Resultado:
        return {"ok": True}

    def poner_clave(self, clave: str) -> Resultado:
        return {"ok": False, "error": "La demo no usa clave de Riot."}

    def abrir_carpeta(self, id_: str) -> Resultado:
        return {"ok": False, "error": SIN_GRABACIONES}

    def abrir_clip(self, id_: str, i: Any) -> Resultado:
        return {"ok": False, "error": SIN_GRABACIONES}

    def salir(self) -> Resultado:
        """Cierra la demo (lo pide el botón de Ajustes); al salir se borra su carpeta."""
        if not self.al_salir:
            return {"ok": False, "error": "Sin ventanas no puedo cerrarme desde aquí."}
        threading.Timer(0.5, self.al_salir).start()
        return {"ok": True}
