"""Ventanas de la app con WebView2 (pywebview): la principal y la que va encima del juego.

Cerrar la principal solo la esconde: la app sigue viva mientras el cliente del LoL esté abierto, para
enseñar el overlay y grabar la siguiente partida. Se cierra sola a los 5 minutos de cerrar el cliente,
salvo con "siempre en marcha" (entonces solo se cierra desde Ajustes o al apagar el PC).
En la demo no hay ventana encima del juego y cerrar la principal cierra la app.
"""

import logging
import threading
import time
from typing import Any

import webview

from . import config, overlay
from .tipos import AppDelPanel

logger = logging.getLogger(__name__)

ANCHO_OVERLAY, ALTO_OVERLAY = 1180, 580
FONDO = "#0a0e15"
MINUTOS_PARA_SALIR = 5


class Ventanas:
    def __init__(self, app: AppDelPanel, url: str, *, titulo: str = "Deep Prep", demo: bool = False) -> None:
        """demo: sin la ventana del overlay (no hay juego encima del que ponerla) y cerrar la principal cierra la app."""
        self.app = app
        self.url = url
        self.titulo = titulo
        self.demo = demo
        self.principal: Any = None  # webview.Window
        self.flotante: Any = None
        self.saliendo = False
        self.oculta_desde: float | None = None  # cuándo se cerró (escondió) la ventana principal

    def arrancar(self, oculta: bool = False) -> None:
        """Bloquea hasta que la app se cierra: el bucle de ventanas tiene que ir en el hilo principal.

        oculta: arranque con Windows; la ventana principal empieza escondida (el acceso directo la enseña).
        """
        cfg = self.app.cfg
        self.principal = webview.create_window(
            self.titulo, self.url, width=1500, height=950, min_size=(1100, 700), background_color=FONDO, hidden=oculta
        )
        if oculta:
            self.oculta_desde = time.time()
        self.principal.events.closing += self._al_cerrar
        if cfg.get("overlay", True) and not self.demo:
            self.flotante = webview.create_window(
                "Deep Prep · partida",
                self.url + "?vista=overlay",
                width=ANCHO_OVERLAY,
                height=ALTO_OVERLAY,
                frameless=True,
                easy_drag=False,
                on_top=True,
                focus=False,
                hidden=True,
                shadow=False,
                background_color=FONDO,
            )
        self.app.al_mostrar = self.mostrar_principal
        self.app.al_salir = self.salir
        self.app.ventana_visible = lambda: self.oculta_desde is None
        icono = config.RUTA_WEB / "icono.ico"
        webview.start(self._en_marcha, icon=str(icono) if icono.exists() else None)

    def _en_marcha(self) -> None:
        if self.flotante:
            hwnd = self._hwnd(self.flotante)
            if hwnd:
                ventana = overlay.VentanaWin32(hwnd, ANCHO_OVERLAY, ALTO_OVERLAY, self.app.cfg.get("overlay_opacidad", 0.94))
                ctl = overlay.Controlador(self.app, ventana)
                threading.Thread(target=ctl.bucle, name="overlay", daemon=True).start()
            else:
                logger.warning("No se pudo preparar la ventana del overlay")
        self._vigilar_salida()

    @staticmethod
    def _hwnd(ventana: Any, espera: float = 20) -> int | None:
        limite = time.time() + espera
        while time.time() < limite:
            nativa = getattr(ventana, "native", None)
            if nativa is not None:
                try:
                    hwnd: int = nativa.Handle.ToInt64()
                    return hwnd
                except Exception:  # noqa: BLE001  mientras se crea la ventana .NET (pythonnet) falla con las suyas; se reintenta
                    pass
            time.sleep(0.2)
        return None

    def _al_cerrar(self) -> bool:
        if self.demo:
            self.saliendo = True  # en la demo, cerrar la ventana es salir
        if self.saliendo:
            return True
        self.oculta_desde = time.time()
        threading.Thread(target=self.principal.hide, daemon=True).start()
        return False  # cancela el cierre: solo se esconde

    def mostrar_principal(self) -> None:
        self.oculta_desde = None
        self.principal.show()
        self.principal.restore()

    def salir(self) -> None:
        self.saliendo = True
        for v in (self.flotante, self.principal):
            if v:
                v.destroy()

    def _vigilar_salida(self) -> None:
        while not self.saliendo:
            time.sleep(5)
            oculta = self.oculta_desde
            if self.app.cfg.get("siempre_en_marcha"):
                continue
            if oculta and self.app.fase is None and time.time() - oculta >= MINUTOS_PARA_SALIR * 60:
                logger.info("Ventana cerrada y cliente del LoL cerrado; cierro.")
                self.salir()
                return
