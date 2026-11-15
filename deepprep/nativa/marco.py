"""La barra de arriba de la ventana es la de la app, y Windows sigue haciendo lo suyo.

La ventana se crea sin marco (Qt.FramelessWindowHint) y aquí se le devuelven los estilos de una ventana normal:
barra de título, borde para cambiar el tamaño y botones de minimizar y maximizar (WS_CAPTION, WS_THICKFRAME...). Así
Windows la trata como a cualquier otra: sombra, esquinas redondeadas de Windows 11, animaciones al minimizar y
maximizar, Win+flechas, encajarla arrastrándola a un borde y el menú de la barra con el botón derecho (o Alt+Espacio).

Un filtro de mensajes nativos hace el resto:
- WM_NCCALCSIZE: toda la ventana es de la app; Windows no pinta su barra ni su borde. Maximizada, Windows la saca un
  poco de la pantalla por cada lado (el grosor del borde): se recorta a la zona de trabajo del monitor.
- WM_NCHITTEST: qué es cada punto. Los bordes cambian el tamaño, la barra arrastra (con doble clic maximiza) y el botón
  de maximizar es HTMAXBUTTON, que en Windows 11 abre el menú de distribuciones al dejar el ratón encima. Lo que la
  interfaz marca como interactivo (búsqueda, botones) y todo lo de debajo de la barra es de la app.
- El botón de maximizar recibe entonces los mensajes de Windows, no los de Qt: su clic y su «ratón encima» llegan
  por aquí y la interfaz los lee de maxEncima y maxPulsado.
"""

import ctypes
import logging
import sys
from ctypes import wintypes as wt
from typing import Any

from PySide6.QtCore import Property, QAbstractNativeEventFilter, QByteArray, QObject, QPointF, QRectF, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQuick import QQuickItem, QQuickWindow

logger = logging.getLogger(__name__)

# Respuestas a WM_NCHITTEST: qué parte de la ventana hay bajo el ratón.
HTCLIENT, HTCAPTION, HTMAXBUTTON = 1, 2, 9
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = range(10, 18)

WM_NCCALCSIZE, WM_NCHITTEST = 0x0083, 0x0084
WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCLBUTTONDBLCLK = 0x00A1, 0x00A2, 0x00A3
WM_NCMOUSELEAVE = 0x02A2
GWL_STYLE = -16
WS_POPUP, WS_CAPTION, WS_SYSMENU, WS_THICKFRAME = 0x80000000, 0x00C00000, 0x00080000, 0x00040000
WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00020000, 0x00010000
# SWP_FRAMECHANGED, sin mover, sin redimensionar, sin cambiar el orden ni activarla.
SWP_MARCO_NUEVO = 0x0020 | 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0200
DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWA_BORDER_COLOR = 20, 33, 34
DWMWCP_ROUND = 2
VK_LBUTTON = 0x01

# Grosor (en píxeles de la interfaz) de la franja de los bordes con la que se cambia el tamaño.
BORDE = 5
# Color del borde de 1 px que Windows 11 pinta alrededor de la ventana (COLORREF, 0x00BBGGRR): el de las líneas del panel.
COLOR_BORDE = 0x002C2B2A


def zona(
    x: float, y: float, ancho: float, alto: float, alto_barra: float, maximizada: bool, sobre_max: bool, sobre_app: bool
) -> int:
    """Lo que Windows tiene que hacer con el ratón en (x, y), en píxeles de la interfaz desde la esquina de la ventana.

    sobre_max: está encima del botón de maximizar; sobre_app: encima de algo interactivo de la barra.
    """
    if not maximizada:
        izq, der, arr, aba = x < BORDE, x >= ancho - BORDE, y < BORDE, y >= alto - BORDE
        if arr and izq:
            return HTTOPLEFT
        if arr and der:
            return HTTOPRIGHT
        if aba and izq:
            return HTBOTTOMLEFT
        if aba and der:
            return HTBOTTOMRIGHT
        if izq:
            return HTLEFT
        if der:
            return HTRIGHT
        if arr:
            return HTTOP
        if aba:
            return HTBOTTOM
    if sobre_max:
        return HTMAXBUTTON
    if sobre_app or y >= alto_barra:
        return HTCLIENT
    return HTCAPTION


class MARGINS(ctypes.Structure):
    _fields_ = [("izq", ctypes.c_int), ("der", ctypes.c_int), ("arr", ctypes.c_int), ("aba", ctypes.c_int)]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wt.RECT * 3), ("lppos", ctypes.c_void_p)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


_u32: Any = None
_dwm: Any = None
if sys.platform == "win32":
    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _dwm = ctypes.WinDLL("dwmapi")
    _u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    _u32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
    _u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    _u32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
    _u32.IsZoomed.argtypes = [wt.HWND]
    _u32.ScreenToClient.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
    _u32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    _u32.MonitorFromWindow.restype = wt.HMONITOR
    _u32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
    _u32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
    _u32.GetAsyncKeyState.restype = ctypes.c_short
    _dwm.DwmSetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
    _dwm.DwmExtendFrameIntoClientArea.argtypes = [wt.HWND, ctypes.POINTER(MARGINS)]


def _atributo(hwnd: int, atributo: int, valor: int) -> None:
    v = ctypes.c_uint(valor)
    _dwm.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(v), ctypes.sizeof(v))  # en Windows 10 algunos fallan: da igual


class _Filtro(QAbstractNativeEventFilter):
    def __init__(self, marco: "Marco") -> None:
        super().__init__()
        self._marco = marco

    def nativeEventFilter(self, tipo: QByteArray | bytes | bytearray | memoryview, mensaje: int) -> object:
        try:
            return self._marco.mensaje(int(mensaje))
        except Exception:  # un fallo aquí no puede tumbar la ventana: Windows hace lo de siempre con ese mensaje
            logger.exception("Fallo en el marco de la ventana")
            return False, 0


class Marco(QObject):
    """La barra de la ventana. La interfaz le dice qué es interactivo y lee el estado del botón de maximizar."""

    cambio = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hwnd = 0
        self._ventana: QQuickWindow | None = None
        self._filtro: _Filtro | None = None
        self._interactivos: list[QQuickItem] = []
        self._boton_max: QQuickItem | None = None
        self._alto_barra = 56.0
        self._integrado = False
        self._max_encima = False
        self._max_pulsado = False
        # Windows no avisa siempre de que el ratón se ha ido del botón de maximizar: se mira cada poco mientras está.
        self._vigia = QTimer(self)
        self._vigia.setInterval(80)
        self._vigia.timeout.connect(self._vigilar_boton)

    # --- lo que lee y llama la interfaz -----------------------------------------------------------
    def _get_integrado(self) -> bool:
        return self._integrado

    def _get_max_encima(self) -> bool:
        return self._max_encima

    def _get_max_pulsado(self) -> bool:
        return self._max_pulsado

    def _get_alto_barra(self) -> float:
        return self._alto_barra

    def _set_alto_barra(self, v: float) -> None:
        self._alto_barra = float(v)

    integrado = Property(bool, _get_integrado, notify=cambio)
    maxEncima = Property(bool, _get_max_encima, notify=cambio)
    maxPulsado = Property(bool, _get_max_pulsado, notify=cambio)
    altoBarra = Property(float, _get_alto_barra, _set_alto_barra)

    @Slot(QQuickItem)
    def interactivo(self, item: QQuickItem) -> None:
        """Algo de la barra que es de la app (no arrastra la ventana): la búsqueda, un botón..."""
        self._interactivos.append(item)

    @Slot(QQuickItem)
    def botonMaximizar(self, item: QQuickItem) -> None:
        self._boton_max = item

    # --- Windows -------------------------------------------------------------------------------------
    def instalar(self, ventana: QQuickWindow) -> bool:
        """Antes de enseñar la ventana. Sin Windows (o si algo falla), la ventana se queda sin marco y sin más."""
        if _u32 is None:
            return False
        try:
            hwnd = int(ventana.winId())
            estilo = _u32.GetWindowLongPtrW(hwnd, GWL_STYLE) & 0xFFFFFFFF
            estilo = (estilo & ~WS_POPUP) | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
            _u32.SetWindowLongPtrW(hwnd, GWL_STYLE, estilo)
            _atributo(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)  # el menú de la barra (Alt+Espacio), oscuro
            _atributo(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
            _atributo(hwnd, DWMWA_BORDER_COLOR, COLOR_BORDE)
            # Con 1 px de marco «dentro» de la ventana, DWM le sigue poniendo la sombra.
            _dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(MARGINS(0, 0, 1, 0)))
        except OSError:
            logger.exception("No se pudo preparar la barra de la ventana")
            return False
        self._hwnd, self._ventana = hwnd, ventana
        self._filtro = _Filtro(self)
        app = QGuiApplication.instance()
        assert isinstance(app, QGuiApplication)
        app.installNativeEventFilter(self._filtro)
        _u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_MARCO_NUEVO)  # que Windows vuelva a preguntar por el marco
        self._integrado = True
        self.cambio.emit()
        return True

    def desinstalar(self) -> None:
        """Al desmontar la ventana: fuera el filtro, que si no seguiría mirando los mensajes de una ventana que ya no está."""
        app = QGuiApplication.instance()
        if self._filtro and app:
            app.removeNativeEventFilter(self._filtro)
        self._filtro, self._hwnd, self._ventana = None, 0, None

    def mensaje(self, direccion: int) -> tuple[bool, int]:
        msg = wt.MSG.from_address(direccion)
        if not self._hwnd or (msg.hWnd or 0) != self._hwnd:
            return False, 0
        m = msg.message
        if m == WM_NCCALCSIZE:
            if msg.wParam and _u32.IsZoomed(self._hwnd):
                self._recortar_maximizada(msg.lParam)
            return True, 0
        if m == WM_NCHITTEST:
            ht = self._zona_en(msg.lParam)
            self._poner(encima=ht == HTMAXBUTTON)
            return True, ht
        if m in (WM_NCLBUTTONDOWN, WM_NCLBUTTONDBLCLK) and msg.wParam == HTMAXBUTTON:
            self._poner(pulsado=True)
            return True, 0
        if m == WM_NCLBUTTONUP and msg.wParam == HTMAXBUTTON:
            if self._max_pulsado:
                QTimer.singleShot(0, self.alternar_maximizada)  # fuera del filtro: cambiar el tamaño manda más mensajes
            self._poner(pulsado=False)
            return True, 0
        if m == WM_NCMOUSELEAVE:
            self._poner(encima=False, pulsado=False)
        return False, 0

    @Slot()
    def alternar_maximizada(self) -> None:
        v = self._ventana
        if v is None:
            return
        if v.visibility() == QWindow.Visibility.Maximized:
            v.showNormal()
        else:
            v.showMaximized()

    def _recortar_maximizada(self, lparam: int) -> None:
        """Maximizada, a la zona de trabajo del monitor (sin la barra de tareas). Con la barra de tareas que se esconde
        sola, se deja 1 px abajo: si la ventana ocupa el monitor entero, Windows no la vuelve a sacar."""
        r = NCCALCSIZE_PARAMS.from_address(lparam).rgrc[0]
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not _u32.GetMonitorInfoW(_u32.MonitorFromWindow(self._hwnd, 2), ctypes.byref(info)):
            return
        w, mon = info.rcWork, info.rcMonitor
        r.left, r.top, r.right, r.bottom = max(r.left, w.left), max(r.top, w.top), min(r.right, w.right), min(r.bottom, w.bottom)
        if (w.left, w.top, w.right, w.bottom) == (mon.left, mon.top, mon.right, mon.bottom):
            r.bottom -= 1

    def _punto(self, x_pantalla: int, y_pantalla: int) -> QPointF:
        """De píxeles de la pantalla a píxeles de la interfaz, desde la esquina de la ventana."""
        p = wt.POINT(x_pantalla, y_pantalla)
        _u32.ScreenToClient(self._hwnd, ctypes.byref(p))
        escala = self._ventana.devicePixelRatio() if self._ventana else 1.0
        return QPointF(p.x / escala, p.y / escala)

    def _zona_en(self, lparam: int) -> int:
        x, y = ctypes.c_short(lparam & 0xFFFF).value, ctypes.c_short((lparam >> 16) & 0xFFFF).value
        p = self._punto(x, y)
        v = self._ventana
        assert v is not None
        maximizada = bool(_u32.IsZoomed(self._hwnd))
        sobre_max = self._encima_de(self._boton_max, p)
        sobre_app = any(self._encima_de(i, p) for i in self._interactivos)
        return zona(p.x(), p.y(), v.width(), v.height(), self._alto_barra, maximizada, sobre_max, sobre_app)

    @staticmethod
    def _encima_de(item: QQuickItem | None, p: QPointF) -> bool:
        if item is None or not item.isVisible():
            return False
        return item.mapRectToScene(QRectF(0, 0, item.width(), item.height())).contains(p)

    def _poner(self, encima: bool | None = None, pulsado: bool | None = None) -> None:
        antes = (self._max_encima, self._max_pulsado)
        if encima is not None:
            self._max_encima = encima
        if pulsado is not None:
            self._max_pulsado = pulsado
        if self._max_encima and not self._vigia.isActive():
            self._vigia.start()
        if (self._max_encima, self._max_pulsado) != antes:
            self.cambio.emit()

    def _vigilar_boton(self) -> None:
        """Mientras el ratón está en el botón de maximizar: si se va, o se suelta el botón fuera, se apaga."""
        c = wt.POINT()
        _u32.GetCursorPos(ctypes.byref(c))
        encima = self._encima_de(self._boton_max, self._punto(c.x, c.y))
        pulsado = self._max_pulsado and bool(_u32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        self._poner(encima=encima, pulsado=pulsado)
        if not encima:
            self._vigia.stop()
