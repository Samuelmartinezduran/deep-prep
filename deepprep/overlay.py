"""El panel encima del juego: cuándo se enseña, dónde se coloca y el atajo de teclado.

Lo que Riot aprueba es superponer datos que ya existían antes de la partida. Por eso aquí:
- La ventana es otra ventana de Windows puesta por encima; no se inyecta nada en el juego ni se lee su memoria.
- El atajo se consulta preguntando a Windows si las teclas están pulsadas: no hay ganchos de teclado.
- La ventana no coge el foco y deja pasar los clics: el juego sigue recibiendo todo.
"""

import configparser
import ctypes
import ctypes.wintypes as wt
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Nombres de tecla que se aceptan en "atajo_overlay" (además de letras, números y F1-F12).
TECLAS = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "mayus": 0x10,
    "alt": 0x12,
    "tab": 0x09,
    "espacio": 0x20,
    "space": 0x20,
    "º": 0xDC,
    "capslock": 0x14,
    "insert": 0x2D,
    "inicio": 0x24,
    "home": 0x24,
    "fin": 0x23,
    "end": 0x23,
    "repag": 0x21,
    "avpag": 0x22,
    "pageup": 0x21,
    "pagedown": 0x22,
}
CLASE_JUEGO = "RiotWindowClass"
MODO_SIN_BORDES = "2"
# Cada cuánto se mira si la partida ha empezado (el reloj del juego): en la pantalla de carga y el resto del tiempo.
MODO_EN_CARGA_S, MODO_CADA_S = 0.2, 1.0


def parsear_atajo(texto: str | None) -> list[int] | None:
    """'ctrl+tab' -> [0x11, 0x09]; None si alguna tecla no se entiende."""
    vks: list[int] = []
    for parte in (texto or "").lower().replace(" ", "").split("+"):
        if parte in TECLAS:
            vks.append(TECLAS[parte])
        elif len(parte) == 1 and parte.isalnum():
            vks.append(ord(parte.upper()))
        elif parte.startswith("f") and parte[1:].isdigit() and 1 <= int(parte[1:]) <= 12:
            vks.append(0x6F + int(parte[1:]))
        else:
            return None
    return vks or None


def debe_verse(modo: str, pulsado: bool) -> bool:
    """En la pantalla de carga se ve solo; ya jugando, solo mientras se mantiene el atajo."""
    return modo == "carga" or (modo == "juego" and pulsado)


def modo_ventana(ruta_lol: str | Path) -> str | None:
    """WindowMode del juego ('0' pantalla completa, '1' ventana, '2' sin bordes) o None si no se sabe."""
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cfg.read(Path(ruta_lol) / "Config" / "game.cfg", encoding="utf-8")
    except (OSError, configparser.Error, UnicodeDecodeError):
        return None
    return cfg.get("General", "WindowMode", fallback=None)


class Controlador:
    """Decide en cada momento si el overlay se ve. Las piezas de Windows se inyectan para poder probarlo."""

    def __init__(
        self,
        app: Any,
        ventana: Any,
        tecla_pulsada: Callable[[int], bool] | None = None,
        juego_delante: Callable[[], bool] | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        """app: la app (su configuración, fase y modo); ventana: algo con mostrar() y ocultar() (y opacidad())."""
        self.app = app
        self.ventana = ventana
        self._atajo: str | None = None
        self._opacidad = app.cfg.get("overlay_opacidad")
        self.vks: list[int] | None = None
        self._pulsada = tecla_pulsada or _tecla_pulsada
        self._juego_delante = juego_delante or juego_delante_win32
        self._reloj = reloj
        self.visible = False
        self._ultimo_modo = 0.0
        self._modo_juego: str | None = None  # WindowMode leído al entrar en partida

    def puede(self) -> bool:
        """Encima de una pantalla completa exclusiva el juego se minimizaría: solo con ventana sin bordes."""
        if not self.app.cfg.get("overlay", True):
            return False
        return self._modo_juego == MODO_SIN_BORDES

    def paso(self) -> None:
        app = self.app
        ahora = self._reloj()
        # Los ajustes se pueden cambiar con la app abierta.
        if app.cfg.get("atajo_overlay") != self._atajo:
            self._atajo = app.cfg.get("atajo_overlay")
            self.vks = parsear_atajo(self._atajo or "ctrl+tab")
        if app.cfg.get("overlay_opacidad") != self._opacidad and hasattr(self.ventana, "opacidad"):
            self._opacidad = app.cfg.get("overlay_opacidad")
            self.ventana.opacidad(self._opacidad or 0.94)
        # El vigía de la app mira el cliente cada 2,5 s; aquí el paso de carga a juego se nota antes. En la carga se
        # mira más a menudo: la vista de carga tiene que irse en cuanto se puede jugar (normas de Riot).
        cada = MODO_EN_CARGA_S if app.modo == "carga" else MODO_CADA_S
        if app.fase is not None and ahora - self._ultimo_modo >= cada:
            self._ultimo_modo = ahora
            antes = app.modo
            app.actualizar_modo()
            if app.modo != "previa" and antes == "previa":
                self._modo_juego = modo_ventana(app.lcu.ruta)
        pulsado = bool(self.vks and all(self._pulsada(vk) for vk in self.vks))
        # Sin el juego delante (cerrado, aún sin ventana o con Alt+Tab a otra cosa) no hay nada que tapar. Por lo
        # mismo, Ctrl+Tab en el navegador con el juego detrás no lo saca.
        quiere = self.puede() and debe_verse(app.modo, pulsado) and self._juego_delante()
        if quiere != self.visible:
            self.visible = quiere
            self.ventana.mostrar() if quiere else self.ventana.ocultar()

    def bucle(self, pausa: float = 0.03) -> None:
        if self._modo_juego is None:
            self._modo_juego = modo_ventana(self.app.lcu.ruta)
        while True:
            try:
                self.paso()
            except Exception:  # el hilo del overlay no puede morir por un fallo suelto
                logger.exception("Fallo en el overlay")
                time.sleep(1)
            time.sleep(pausa)


# --- Windows ------------------------------------------------------------------------------------
# user32 de Windows (fuera de Windows, None: así el módulo se puede importar para probar Controlador).
_u32: Any = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_LAYERED, WS_EX_NOACTIVATE = 0x20, 0x80, 0x80000, 0x8000000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
LWA_ALPHA = 0x2
HWND_TOPMOST = wt.HWND(-1)

if _u32:
    _u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    _u32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
    _u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    _u32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _u32.FindWindowW.restype = wt.HWND
    _u32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
    _u32.GetForegroundWindow.restype = wt.HWND
    _u32.GetWindowThreadProcessId.restype = wt.DWORD
    _u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]


def _tecla_pulsada(vk: int) -> bool:
    return bool(_u32.GetAsyncKeyState(vk) & 0x8000)


def rect_del_juego() -> tuple[int, int, int, int] | None:
    """(x, y, ancho, alto) de la ventana del juego, o None si no está abierta."""
    hwnd = _u32.FindWindowW(CLASE_JUEGO, None)
    if not hwnd:
        return None
    r = wt.RECT()
    if not _u32.GetWindowRect(hwnd, ctypes.byref(r)) or r.right - r.left < 200:
        return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def _proceso(hwnd: int) -> int:
    pid = wt.DWORD()
    _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def juego_delante_win32() -> bool:
    """¿La ventana del juego está abierta y es la que tienes delante? (De su mismo proceso también vale.)"""
    if rect_del_juego() is None:
        return False
    juego, delante = _u32.FindWindowW(CLASE_JUEGO, None), _u32.GetForegroundWindow()
    return bool(juego and delante) and (delante == juego or _proceso(delante) == _proceso(juego))


class VentanaWin32:
    """Ventana de Windows ya creada (la del overlay): siempre encima, sin foco, transparente al ratón."""

    def __init__(self, hwnd: int, ancho: int, alto: int, opacidad: float) -> None:
        self.hwnd = wt.HWND(hwnd)
        self.ancho, self.alto = ancho, alto
        ex = _u32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        _u32.SetWindowLongPtrW(
            self.hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        )
        self.opacidad(opacidad)

    def opacidad(self, valor: float) -> None:
        _u32.SetLayeredWindowAttributes(self.hwnd, 0, max(60, min(255, int(255 * valor))), LWA_ALPHA)

    def _colocar(self) -> None:
        # Centrada sobre el juego, algo por debajo del borde de arriba (deja ver el marcador del juego).
        juego = rect_del_juego() or (0, 0, _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1))
        x = juego[0] + (juego[2] - self.ancho) // 2
        y = juego[1] + max(0, int(juego[3] * 0.07))
        _u32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, self.ancho, self.alto, SWP_NOACTIVATE)

    def mostrar(self) -> None:
        self._colocar()
        _u32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        _u32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def ocultar(self) -> None:
        _u32.ShowWindow(self.hwnd, SW_HIDE)
