"""Formas de los datos que pasan de un módulo a otro (y al panel, como JSON).

Lo que viene de Riot y lo que se guarda en la caché son diccionarios grandes que pasan tal cual: se nombran con un
alias que dice qué son, y sus claves se explican donde se crean. Lo pequeño y fijo va como TypedDict. Nada de esto
cambia el JSON: son solo tipos. Al final, AppDelPanel: lo que el servidor y las ventanas necesitan de la app.
"""

from collections.abc import Callable
from typing import Any, NotRequired, Protocol, TypedDict

Json = dict[str, Any]  # un objeto JSON cualquiera (lo que da la API de Riot, o del cliente del LoL)
Cfg = dict[str, Any]  # la configuración en uso (config.POR_DEFECTO y lo que haya en config.json)
Partida = dict[str, Any]  # analisis.reducir_partida: id, creacion, duracion, cola, mapa, remake, equipos, jug
Jugador = dict[str, Any]  # uno de Partida["jug"]: puuid, pid, equipo, campeon, pos, gana, k, d, a, ch...
Linea = dict[str, Any]  # analisis.reducir_linea o revision.reducir_linea_completa: pos, est, kills, monstruos
Registro = dict[str, Any]  # duelos.extraer: el duelo de un jugador contra su rival de posición en una partida
Panel = dict[str, Any]  # sesion.Sesion.panel: lo que enseña el panel de una partida en vivo
Revision = dict[str, Any]  # revision.revisar, con lo que añade revisiones.Revisor (referencia, lp, carpeta, icono)
Cancelada = Callable[[], bool]  # si la tarea que pide algo a Riot ya no hace falta (deja de esperar cuota)


class Resultado(TypedDict):
    """Lo que devuelven las acciones del panel: si ha ido bien y, si no, por qué."""

    ok: bool
    error: NotRequired[str]
    pendiente: NotRequired[bool]  # la clave nueva aún no vale: Riot tarda un poco en activarla


class Tarjeta(TypedDict):
    """Una tarjeta del perfil del jungla rival. tono: 'ojo', 'bien' o 'neutro', desde tu punto de vista."""

    titulo: str
    valor: str
    detalle: str
    tono: str


class Etiqueta(TypedDict):
    """Una etiqueta corta de un jugador (OTP, Racha +3...). tono: 'fuerte', 'flojo' o 'neutro', sobre él."""

    t: str
    tono: str
    d: str


class Aviso(TypedDict):
    tono: str
    texto: str


class Sync(TypedDict):
    """Partidas propias que faltan por bajar (hechas de total)."""

    hechas: int
    total: int


class LigaUI(TypedDict):
    """La liga de un jugador tal y como sale en el panel."""

    nivel: str
    rank: str
    txt: str
    lp: int
    v: int
    d: int


class EstadoVersion(TypedDict):
    """La versión de la app y la nueva, si hay una descargada y lista para instalar."""

    version: str
    nueva: str | None
    lista: bool
    error: str


class _ConVersion(Protocol):
    """Los datos de campeones, tal y como los usa el servidor: la versión de Data Dragon de las imágenes."""

    @property
    def version(self) -> str: ...


class _ConNovedades(Protocol):
    def novedades_vistas(self) -> Resultado: ...


class AppDelPanel(Protocol):
    """Lo que usan de la app el servidor del panel y las ventanas: la de verdad (app.App) o la de la demo
    (demo.AppDemo). Si el panel pide algo nuevo a la app, mypy obliga a que la demo también lo tenga."""

    cfg: Cfg
    al_mostrar: Callable[[], None] | None
    al_salir: Callable[[], None] | None
    ventana_visible: Callable[[], bool] | None

    @property
    def fase(self) -> str | None: ...

    @property
    def datos(self) -> _ConVersion: ...

    @property
    def actualizador(self) -> _ConNovedades: ...

    def estado(self, contar: bool = True) -> Json: ...

    def revisiones(self) -> Json: ...

    def revision(self, id_: str) -> Revision | None: ...

    def ajustes(self) -> Json: ...

    def guardar_ajustes(self, cambios: Any) -> Resultado: ...

    def buscar(self, rid: str) -> Resultado: ...

    def volver(self) -> Resultado: ...

    def poner_clave(self, clave: str) -> Resultado: ...

    def abrir_carpeta(self, id_: str) -> Resultado: ...

    def abrir_clip(self, id_: str, i: Any) -> Resultado: ...

    def salir(self) -> Resultado: ...
