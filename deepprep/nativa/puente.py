"""Lo que la interfaz nativa lee de la app y lo que le pide.

- El estado: se pregunta a la app cada segundo (app.estado), en otro hilo para no frenar la
  ventana. Solo si ha cambiado se rehacen las vistas (vistas.py) y se avisa a la interfaz (estadoCambiado).
- Lo que se pide: puente.llamar("buscar", [riot_id], r => ...). Va a un hilo aparte (buscar a un jugador o guardar
  los ajustes pueden tardar: hablan con Riot) y la respuesta vuelve al hilo de la interfaz, a esa función. Solo se
  puede pedir lo que hay en acciones().
- Las imágenes de Data Dragon: image://ddragon/<tipo>/<clave>, de su caché en disco (ddragon.imagen).
"""

import json
import logging
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import Property, QObject, QRunnable, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QJSEngine, QJSValue
from PySide6.QtQuick import QQuickAsyncImageProvider, QQuickImageResponse, QQuickTextureFactory

from .. import ddragon
from ..tipos import AppDelPanel, Json, Revision
from . import vistas

logger = logging.getLogger(__name__)

# Cada cuánto se pregunta el estado a la app.
CADA_S = 1.0


class Puente(QObject):
    """La app, para la interfaz. oro_de(revisión) da la diferencia de oro de esa partida (None si no se sabe)."""

    estadoCambiado = Signal()
    _nuevoEstado = Signal(object)
    _hecho = Signal(int, object)

    def __init__(
        self, app: AppDelPanel, oro_de: Callable[[Revision], Sequence[int] | None], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._app = app
        self._oro_de = oro_de
        self._motor: QJSEngine | None = None
        self._comun: Json = {}
        self._partida: Json = {}
        self._overlay: Json = {"esperando": True}
        self._modo = "previa"
        self._inicio = 0.0
        self._ultimo = ""
        self._campeones: list[Json] = []
        self._turno = 0
        self._esperando: dict[int, QJSValue] = {}
        self._trabajo = ThreadPoolExecutor(max_workers=4, thread_name_prefix="puente")
        self._despertar = threading.Event()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._nuevoEstado.connect(self._poner_estado, Qt.ConnectionType.QueuedConnection)
        self._hecho.connect(self._entregar, Qt.ConnectionType.QueuedConnection)

    # --- el estado -------------------------------------------------------------------------------------------
    def arrancar(self, motor: QJSEngine) -> None:
        """Con el motor de QML (para devolverle las respuestas) empieza a mirar el estado."""
        self._motor = motor
        self.refrescar()
        self._hilo = threading.Thread(target=self._mirar, name="puente-estado", daemon=True)
        self._hilo.start()

    def parar(self) -> None:
        """Deja de mirar el estado y espera a que el hilo acabe: después nadie avisa a la interfaz (que se destruye)."""
        self._parar.set()
        self._despertar.set()
        self._trabajo.shutdown(wait=False, cancel_futures=True)
        if self._hilo and self._hilo is not threading.current_thread():
            self._hilo.join(timeout=3)

    def refrescar(self) -> None:
        """Lee el estado ya (en el hilo en el que se llame) y, si ha cambiado, rehace las vistas."""
        try:
            e = self._app.estado()
        except Exception:  # un fallo de la app no puede tumbar la interfaz: se vuelve a intentar al poco
            logger.exception("No se pudo leer el estado de la app")
            return
        texto = json.dumps(e, sort_keys=True, ensure_ascii=False, default=str)
        if texto == self._ultimo:
            return
        self._ultimo = texto
        self._nuevoEstado.emit(self.vistas_de(e))

    @staticmethod
    def vistas_de(e: Json) -> Json:
        reloj = e.get("reloj")
        p = e.get("panel")
        if reloj:
            inicio = time.time() * 1000 - float(reloj) * 1000
        else:
            inicio = float(p["inicio"]) if p and not p.get("terminada") and e.get("modo") == "juego" and p.get("inicio") else 0.0
        return {
            "comun": vistas.comun(e),
            "partida": vistas.partida(e),
            "overlay": vistas.overlay(e),
            "modo": e.get("modo") or "previa",
            "inicio": inicio,
        }

    def _mirar(self) -> None:
        while not self._parar.is_set():
            self._despertar.wait(CADA_S)
            self._despertar.clear()
            if not self._parar.is_set():
                self.refrescar()

    @Slot(object)
    def _poner_estado(self, v: Json) -> None:
        self._comun, self._partida, self._overlay = v["comun"], v["partida"], v["overlay"]
        self._modo, self._inicio = v["modo"], v["inicio"]
        self.estadoCambiado.emit()

    def _get_comun(self) -> Json:
        return self._comun

    def _get_partida(self) -> Json:
        return self._partida

    def _get_overlay(self) -> Json:
        return self._overlay

    def _get_modo(self) -> str:
        return self._modo

    def _get_inicio(self) -> float:
        return self._inicio

    comun = Property(dict, _get_comun, notify=estadoCambiado)
    partida = Property(dict, _get_partida, notify=estadoCambiado)
    overlay = Property(dict, _get_overlay, notify=estadoCambiado)
    modo = Property(str, _get_modo, notify=estadoCambiado)
    inicioPartida = Property(float, _get_inicio, notify=estadoCambiado)  # ms desde 1970; 0 = sin reloj

    # --- lo que se pide -------------------------------------------------------------------------------------
    def acciones(self) -> dict[str, Callable[..., Any]]:
        """Lo único que la interfaz puede pedir. Las que cambian el estado lo vuelven a leer en seguida."""
        a = self._app
        escena = getattr(a, "elegir_escena", None)
        return {
            "revisiones": lambda: vistas.revisiones(a.revisiones()),
            "revision": self._revision,
            "ajustes": self._ajustes,
            "guardarAjustes": self._guardar_ajustes,
            "buscar": lambda rid: self._y_refrescar(a.buscar(str(rid))),
            "rol": lambda rol: self._y_refrescar(a.elegir_rol(str(rol))),
            "volver": lambda: self._y_refrescar(a.volver()),
            "clave": lambda clave: self._y_refrescar(a.poner_clave(str(clave))),
            "carpeta": lambda id_: a.abrir_carpeta(str(id_)),
            "clip": lambda id_, i: a.abrir_clip(str(id_), int(i)),
            "novedadesVistas": lambda: self._y_refrescar(a.actualizador.novedades_vistas()),
            "actualizar": lambda: a.actualizador.actualizar_ahora(),
            "salir": a.salir,
            "escena": (lambda id_: self._y_refrescar(escena(str(id_))))
            if escena
            else (lambda id_: {"ok": False, "error": "Solo en la demo."}),
        }

    @Slot(str)
    def copiar(self, texto: str) -> None:
        """Al portapapeles (el nombre de un jugador, para buscarlo luego en op.gg o donde sea)."""
        QGuiApplication.clipboard().setText(texto)

    @Slot(str, "QVariantList", QJSValue)
    def llamar(self, nombre: str, args: list[Any], respuesta: QJSValue) -> None:
        accion = self.acciones().get(nombre)
        if accion is None:
            logger.warning("La interfaz ha pedido algo que no existe: %r", nombre)
            return
        self._turno += 1
        turno = self._turno
        if respuesta.isCallable():
            self._esperando[turno] = respuesta
        self._trabajo.submit(self._hacer, turno, nombre, accion, list(args or []))

    def _hacer(self, turno: int, nombre: str, accion: Callable[..., Any], args: list[Any]) -> None:
        try:
            r = accion(*args)
        except Exception as e:
            logger.exception("Falló %s", nombre)
            r = {"ok": False, "error": f"No se ha podido: {e}"}
        self._hecho.emit(turno, r)

    @Slot(int, object)
    def _entregar(self, turno: int, r: Any) -> None:
        cb = self._esperando.pop(turno, None)
        if cb is not None and self._motor is not None:
            cb.call([self._motor.toScriptValue(r)])

    def _y_refrescar(self, r: Any) -> Any:
        self._despertar.set()
        return dict(r) if isinstance(r, dict) else r

    def _revision(self, id_: str) -> Json | None:
        r = self._app.revision(str(id_))
        return vistas.detalle(r, self._oro_de(r)) if r else None

    def _ajustes(self) -> Json:
        a = self._app.ajustes()
        self._campeones = list(a.get("campeones") or [])
        return vistas.ajustes(a)

    def _guardar_ajustes(self, f: dict[str, Any]) -> Json:
        """Del formulario de la interfaz a lo que guarda la app (ajustes.Ajustes comprueba cada valor)."""
        if not self._campeones:
            self._campeones = list(self._app.ajustes().get("campeones") or [])

        def lineas(txt: Any) -> list[str]:
            return [x.strip() for x in str(txt or "").split("\n") if x.strip()]

        def filas(lista: Any) -> list[tuple[str, str]]:
            return [(str(x.get("campeon", "")), str(x.get("texto", ""))) for x in lista or []]

        cambios = {
            "overlay": bool(f.get("overlay")),
            "atajo_overlay": str(f.get("atajo", "")),
            "overlay_opacidad": int(f.get("opacidad", 94)) / 100,
            "grabar": bool(f.get("grabar")),
            "grabacion_codificador": str(f.get("codificador", "auto")),
            "grabacion_max_gb": str(f.get("max_gb", "0")),
            "siempre_en_marcha": bool(f.get("siempre")),
            "comparar_con": str(f.get("comparar_con", "")),
            "perfil_base": str(f.get("perfil", "")),
            "referencias": vistas.leer_filas(filas(f.get("referencias")), self._campeones),
            "cuentas": lineas(f.get("cuentas")),
            "recordatorios": lineas(f.get("reglas")),
            "notas": vistas.leer_filas(filas(f.get("notas")), self._campeones),
        }
        # Tu rol y los modos, si vienen en el formulario.
        if f.get("rol"):
            cambios["rol"] = str(f["rol"])
        if f.get("modos"):
            cambios["modos"] = {str(m.get("k", "")): bool(m.get("activo")) for m in f["modos"]}
        r = dict(self._app.guardar_ajustes(cambios))
        if r.get("ok"):
            r["ajustes"] = self._ajustes()  # así se ve el estado de las referencias nuevas
        self._despertar.set()
        return r


def imagen_ddragon(id_: str, version: str) -> QImage:
    """La imagen de image://ddragon/<id_> (de la caché en disco o recién bajada). Sin red, una transparente de 1 px:
    queda el hueco del retrato."""
    tipo, _, clave = id_.partition("/")
    datos = ddragon.imagen(tipo, clave, version)
    img = QImage.fromData(datos) if datos else QImage()
    if img.isNull():
        img = QImage(1, 1, QImage.Format.Format_ARGB32)
        img.fill(0)
    return img


class _Respuesta(QQuickImageResponse):
    def __init__(self) -> None:
        super().__init__()
        self._img = QImage()

    def terminar(self, img: QImage) -> None:
        self._img = img
        self.finished.emit()  # Qt deja emitirla desde cualquier hilo

    def textureFactory(self) -> QQuickTextureFactory:
        return QQuickTextureFactory.textureFactoryForImage(self._img)


class _Carga(QRunnable):
    def __init__(self, respuesta: _Respuesta, id_: str, version: str) -> None:
        super().__init__()
        self._respuesta, self._id, self._version = respuesta, id_, version

    def run(self) -> None:
        self._respuesta.terminar(imagen_ddragon(self._id, self._version))


class ImagenesDdragon(QQuickAsyncImageProvider):
    """image://ddragon/<tipo>/<clave>. Cada imagen en su hilo (hasta 6 a la vez): con la caché vacía, las que hay que
    bajar no frenan al resto de imágenes de la interfaz, que Qt carga en una sola cola."""

    def __init__(self, version: str) -> None:
        super().__init__()
        self._version = version
        self._hilos = QThreadPool()
        self._hilos.setMaxThreadCount(6)

    def requestImageResponse(self, id_: str, pedido: QSize) -> QQuickImageResponse:
        r = _Respuesta()
        self._hilos.start(_Carga(r, id_, self._version))
        return r

    def parar(self, espera_ms: int = 5000) -> None:
        """Al cerrar: fuera lo que aún no ha empezado, y se espera a lo que se está bajando. Si no, una imagen podría
        guardarse en la carpeta de datos después de borrarla (la de la demo, al salir)."""
        self._hilos.clear()
        self._hilos.waitForDone(espera_ms)


def precargar(urls: Sequence[str], version: str) -> None:
    """Baja a la caché las imágenes que se van a ver, antes de abrir la ventana (para las capturas)."""
    for u in urls:
        tipo, _, clave = u.removeprefix("image://ddragon/").partition("/")
        if tipo and clave:
            ddragon.imagen(tipo, clave, version)
