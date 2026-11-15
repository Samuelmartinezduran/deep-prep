"""Las ventanas de la app con Qt Quick: la principal y la que va encima del juego.

- Cerrar la principal solo la esconde: la app sigue mientras el cliente del LoL esté abierto, para enseñar el overlay
  y grabar la siguiente partida. Se cierra sola cuando la ventana lleva al menos MINUTOS_PARA_SALIR escondida y el
  cliente está cerrado, salvo con «siempre en marcha». En la demo, cerrar la ventana es salir.
- La ventana encima del juego: cuándo se ve lo decide overlay.Controlador (las normas de Riot); aquí VentanaQt la
  enseña, la esconde y la coloca. Con estilos de Win32 puestos desde fuera (WS_EX_LAYERED...), Qt deja de pintarla:
  aquí lo hace Qt (la ventana ya nace sin foco, transparente al ratón y siempre encima, y la opacidad es la suya).
- Otra copia que arranca (el acceso directo) le pide a esta que enseñe su ventana: app.al_mostrar. Llega desde el
  hilo del servidor, así que todo lo que toca las ventanas pasa al hilo de la interfaz con una señal.
"""

import logging
import os
import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QMessageLogContext,
    QObject,
    Qt,
    QTimer,
    QtMsgType,
    Signal,
    Slot,
    qInstallMessageHandler,
)
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickWindow

from .. import config, overlay
from ..tipos import AppDelPanel, Revision
from . import vistas
from .marco import Marco
from .puente import ImagenesDdragon, Puente

logger = logging.getLogger(__name__)

AQUI = Path(__file__).resolve().parent
RUTA_QML = AQUI / "qml"
RUTA_FUENTES = AQUI / "fuentes"
MINUTOS_PARA_SALIR = 5
ANCHO_OVERLAY, ALTO_OVERLAY = 1180, 580
# Las cachés de Qt (QML compilado y lo preparado para la gráfica): en la carpeta de datos de la app (la de la demo,
# en la demo), y no en la que elegiría Qt, %LOCALAPPDATA%\Deep Prep.
CACHE_QT = config.DATOS / "qt"


def cache_de_pipelines(ventana: QQuickWindow, nombre: str) -> None:
    """La caché de lo que Qt prepara para la gráfica (acelera la siguiente vez que se abre), en la carpeta de datos y
    no en la que elegiría Qt (ver CACHE_QT). Antes de enseñar la ventana."""
    CACHE_QT.mkdir(parents=True, exist_ok=True)
    archivo = str(CACHE_QT / f"pipelines-{nombre}.bin")
    g = ventana.graphicsConfiguration()
    g.setAutomaticPipelineCache(False)
    g.setPipelineCacheSaveFile(archivo)
    g.setPipelineCacheLoadFile(archivo)
    ventana.setGraphicsConfiguration(g)


def al_registro(tipo: QtMsgType, contexto: QMessageLogContext, texto: str) -> None:
    """Los avisos de Qt (un error en una pieza de QML, un archivo que falta) al registro de la app."""
    if tipo == QtMsgType.QtDebugMsg:
        return
    nivel = logging.WARNING if tipo in (QtMsgType.QtWarningMsg, QtMsgType.QtInfoMsg) else logging.ERROR
    logger.log(nivel, "Qt: %s", texto)


def oro_guardado(r: Revision) -> list[int] | None:
    """La diferencia de oro minuto a minuto que guarda la revisión (sin ella, sin gráfico)."""
    d = r.get("dif_oro")
    return [int(x) for x in d] if isinstance(d, list) and d else None


class VentanaQt(QObject):
    """La ventana del overlay para overlay.Controlador (mostrar, ocultar, opacidad), desde cualquier hilo."""

    _orden = Signal(str, float)

    def __init__(self, ventana: QQuickWindow, ancho: int, alto: int, opacidad: float) -> None:
        super().__init__()
        self._v = ventana
        self.ancho, self.alto = ancho, alto
        self._orden.connect(self._hacer, Qt.ConnectionType.QueuedConnection)
        self.opacidad(opacidad)

    def opacidad(self, valor: float) -> None:
        self._orden.emit("opacidad", float(valor))

    def mostrar(self) -> None:
        self._orden.emit("mostrar", 0.0)

    def ocultar(self) -> None:
        self._orden.emit("ocultar", 0.0)

    @Slot(str, float)
    def _hacer(self, que: str, valor: float) -> None:
        v = self._v
        if que == "opacidad":
            v.setOpacity(max(60 / 255, min(1.0, valor)))
        elif que == "mostrar":
            # Centrada sobre el juego, algo por debajo del borde de arriba (deja ver el marcador del juego).
            pantalla = v.screen()  # la del juego, o la principal
            escala = pantalla.devicePixelRatio()
            juego = overlay.rect_del_juego()  # en píxeles de la pantalla: a los de Qt
            if juego:
                x, y, w, h = (c / escala for c in juego)
            else:
                g = pantalla.geometry()
                x, y, w, h = g.x(), g.y(), g.width(), g.height()
            v.setGeometry(int(x + (w - self.ancho) / 2), int(y + max(0, h * 0.07)), self.ancho, self.alto)
            v.show()
            v.raise_()
        elif que == "ocultar":
            v.hide()


class VentanasQt(QObject):
    """La app con la interfaz nativa. arrancar() bloquea hasta que la app se cierra (el bucle de Qt va en el hilo
    principal). demo: sin overlay encima del juego (se ve con «Ver el overlay») y cerrar es salir."""

    _mostrar = Signal()
    _salir = Signal()

    def __init__(
        self,
        app: AppDelPanel,
        *,
        titulo: str = "Deep Prep",
        demo: bool = False,
        vista: str = "partida",
        oro_de: Callable[[Revision], Sequence[int] | None] | None = None,
        minuto_fijo: float = -1.0,
    ) -> None:
        super().__init__()
        self.app = app
        self.titulo = titulo
        self.demo = demo
        self.vista = vista if vista in vistas.TITULOS else "partida"
        self.oro_de = oro_de or oro_guardado
        self.minuto_fijo = minuto_fijo
        self.saliendo = False
        self.oculta_desde: float | None = None
        self.principal: QQuickWindow | None = None
        self.flotante: QQuickWindow | None = None
        self.puente: Puente | None = None
        self.marco = Marco()
        self.motor: QQmlApplicationEngine | None = None
        self._imagenes: ImagenesDdragon | None = None
        self._componentes: list[QQmlComponent] = []
        self._mostrar.connect(self.mostrar_principal, Qt.ConnectionType.QueuedConnection)
        self._salir.connect(self.salir, Qt.ConnectionType.QueuedConnection)

    # --- montar ----------------------------------------------------------------------------------------------
    def preparar(self) -> QQuickWindow:
        """La aplicación de Qt, el motor de QML y las ventanas, sin enseñarlas. Devuelve la principal."""
        # Texto como el de Windows (DirectWrite): más nítido en letra pequeña que el que Qt Quick dibuja por defecto.
        QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
        qapp = QGuiApplication.instance() or QGuiApplication(sys.argv)
        assert isinstance(qapp, QGuiApplication)
        qapp.setApplicationName("Deep Prep")
        qapp.setQuitOnLastWindowClosed(False)  # cerrar la ventana la esconde; se sale con salir()
        qapp.setWindowIcon(QIcon(str(config.RUTA_RECURSOS / "icono.ico")))
        for f in sorted(RUTA_FUENTES.glob("*.ttf")):
            if QFontDatabase.addApplicationFont(str(f)) < 0:
                logger.warning("No se pudo cargar la fuente %s", f.name)
        self.puente = Puente(self.app, self.oro_de)
        # La caché de QML de Qt, en la carpeta de datos (si no, iría a %LOCALAPPDATA%\Deep Prep, aparte; en la demo,
        # fuera de su carpeta temporal).
        os.environ.setdefault("QML_DISK_CACHE_PATH", str(CACHE_QT / "qmlcache"))
        motor = self.motor = QQmlApplicationEngine()
        self._imagenes = ImagenesDdragon(self.app.datos.version)
        motor.addImageProvider("ddragon", self._imagenes)
        ctx = motor.rootContext()
        ctx.setContextProperty("puente", self.puente)
        ctx.setContextProperty("marco", self.marco)
        ctx.setContextProperty("ventanas", self)
        ctx.setContextProperty("vistaInicial", self.vista)
        ctx.setContextProperty("tituloVentana", self.titulo)
        ctx.setContextProperty("escenasDemo", vistas.ESCENAS)
        ctx.setContextProperty("overlayPrevia", self.demo)
        ctx.setContextProperty("minutoFijo", self.minuto_fijo)
        motor.addImportPath(str(RUTA_QML))
        self.puente.arrancar(motor)  # antes de cargar: la interfaz pide cosas nada más crearse
        motor.loadFromModule("DeepPrep", "Principal")
        if not motor.rootObjects():
            raise RuntimeError("No se pudo cargar la interfaz (Principal.qml)")
        principal = motor.rootObjects()[0]
        assert isinstance(principal, QQuickWindow)
        self.principal = principal
        cache_de_pipelines(principal, "principal")
        if self.demo or self.app.cfg.get("overlay", True):
            c = QQmlComponent(motor)
            c.loadFromModule("DeepPrep", "Overlay")
            flotante = c.create(ctx)
            if isinstance(flotante, QQuickWindow):
                self._componentes.append(c)
                self.flotante = flotante
                cache_de_pipelines(flotante, "overlay")
            else:
                logger.warning("No se pudo crear la ventana del overlay: %s", c.errorString())
        return principal

    def arrancar(self, oculta: bool = False) -> int:
        """oculta: arranque con Windows; la ventana principal empieza escondida (el acceso directo la enseña)."""
        qInstallMessageHandler(al_registro)  # el .exe no tiene consola: lo que diga Qt, a deepprep.log
        principal = self.preparar()
        self.app.al_mostrar = self._mostrar.emit
        self.app.al_salir = self._salir.emit
        self.app.ventana_visible = lambda: self.oculta_desde is None
        self.marco.instalar(principal)
        if oculta:
            self.oculta_desde = time.time()
        else:
            principal.show()
        if self.flotante and not self.demo:
            ventana = VentanaQt(self.flotante, ANCHO_OVERLAY, ALTO_OVERLAY, self.app.cfg.get("overlay_opacidad", 0.94))
            ctl = overlay.Controlador(self.app, ventana)
            threading.Thread(target=ctl.bucle, name="overlay", daemon=True).start()
        threading.Thread(target=self._vigilar_salida, name="salida", daemon=True).start()
        qapp = QGuiApplication.instance()
        assert isinstance(qapp, QGuiApplication)
        try:
            return qapp.exec()
        finally:
            self.desmontar()

    def desmontar(self) -> None:
        """Fuera las ventanas y el motor de QML y, después, el puente. En este orden: si Python recoge antes el puente, el
        QML que aún vive avisa de que no lo encuentra (al salir iría a deepprep.log; en las pruebas, a la siguiente)."""
        self.marco.desinstalar()
        if self._imagenes:  # antes que el motor, que se lo lleva
            self._imagenes.parar()
            self._imagenes = None
        for objeto in (self.flotante, self.motor):  # el motor se lleva sus ventanas (la principal)
            if objeto is not None:
                objeto.deleteLater()
        self.flotante, self.motor, self.principal = None, None, None
        self._componentes.clear()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if self.puente:
            self.puente.parar()

    # --- lo que pide la interfaz -----------------------------------------------------------------------------
    @Slot(result=bool)
    def cerrar(self) -> bool:
        """Al cerrar la ventana principal (la X, Alt+F4): en la demo o saliendo, se cierra; si no, solo se esconde."""
        if self.demo:
            self.saliendo = True
        if self.saliendo:
            QTimer.singleShot(0, self.salir)
            return True
        self.oculta_desde = time.time()
        if self.principal:
            # Con la ventana de contexto: si ya no está cuando toque (al desmontar), no se hace nada.
            QTimer.singleShot(0, self.principal, self.principal.hide)
        return False

    @Slot()
    def verOverlay(self) -> None:
        """En la demo, el overlay en una ventana normal, para verlo sin juego."""
        if self.flotante:
            self.flotante.show()
            self.flotante.raise_()
            self.flotante.requestActivate()

    def _get_demo(self) -> bool:
        return self.demo

    esDemo = Property(bool, _get_demo, constant=True)

    # --- mostrar y salir (desde cualquier hilo, por las señales) ---------------------------------------------
    @Slot()
    def mostrar_principal(self) -> None:
        self.oculta_desde = None
        v = self.principal
        if v is None:
            return
        if v.visibility() == QWindow.Visibility.Minimized:
            v.showNormal()
        v.show()
        v.raise_()
        v.requestActivate()

    @Slot()
    def salir(self) -> None:
        self.saliendo = True
        for v in (self.flotante, self.principal):
            if v:
                v.hide()
        qapp = QGuiApplication.instance()
        if qapp:
            qapp.quit()

    def _vigilar_salida(self) -> None:
        while not self.saliendo:
            time.sleep(5)
            oculta = self.oculta_desde
            if self.app.cfg.get("siempre_en_marcha"):
                continue
            if oculta and self.app.fase is None and time.time() - oculta >= MINUTOS_PARA_SALIR * 60:
                logger.info("Ventana cerrada y cliente del LoL cerrado; cierro.")
                self._salir.emit()
                return


def capturar(
    app: AppDelPanel, salida: Path, ancho: int = 1500, alto: int = 950, *, overlay_: bool = False, **opciones: Any
) -> int:
    """Una captura de la ventana (o del overlay) sin enseñarla: para revisar el diseño y para el README."""
    v = VentanasQt(app, **opciones)
    principal = v.preparar()
    ventana = v.flotante if overlay_ and v.flotante else principal
    if ventana is not principal:
        ventana.resize(ANCHO_OVERLAY, ALTO_OVERLAY)
    else:
        ventana.resize(ancho, alto)
    qapp = QGuiApplication.instance()
    assert isinstance(qapp, QGuiApplication)

    def hacer() -> None:
        ventana.grabWindow().save(str(salida))
        print(f"Captura en {salida}")
        qapp.quit()

    QTimer.singleShot(2500, hacer)  # que lleguen el estado, las revisiones y las imágenes
    try:
        return qapp.exec()
    finally:
        v.desmontar()
