"""Núcleo: junta las piezas de la app y da el estado al panel, al overlay y a las ventanas.

Cada pieza hace una cosa y App las conecta:
- cuentas.Cuentas: la clave de la API y tus cuentas.
- partidas.Partidas: partidas y líneas de tiempo (sin pedir dos veces la misma) y tu historial de la temporada.
- comparador.Comparador: tus duelos medidos en partidas de Master+ y con quién te comparas.
- vigia.Vigia y vigia.Sesiones: el cliente del LoL y qué partida enseña el panel.
- seleccion.Seleccion: lo que se enseña en la selección de campeón.
- revisiones.Revisor: la revisión de tu partida al acabar, los LP y los clips.
- ajustes.Ajustes: lo que se cambia desde el panel.
"""

import logging
import threading
import time

from . import actualizador, config, inicio_windows, lcu
from . import analisis as an
from . import recolector as rec
from .ajustes import Ajustes
from .base_duelos import BaseDuelos
from .cache import Cache
from .comparador import Comparador
from .constantes import GRIETA
from .cuentas import Cuentas
from .ddragon import Datos
from .grabacion import Grabador
from .overlay import MODO_SIN_BORDES, modo_ventana
from .partidas import Partidas
from .revisiones import Revisor
from .riot import ClaveInvalida, Cliente, ErrorRiot
from .seleccion import Seleccion
from .sesion import Sesion
from .trabajo import Cola
from .vigia import EN_JUEGO, FASES, PARTIDA_CERCA, Sesiones, Vigia

logger = logging.getLogger(__name__)


def sin_arranque_windows(encendido):
    """Para las pruebas y las herramientas: el arranque con Windows no se toca."""
    return ""


class App:
    """La app: sus piezas y lo que piden el servidor del panel, las ventanas, el overlay y el actualizador.

    Las piezas de fuera (configuración, caché, datos de campeones, API de Riot, cliente del LoL, base de duelos,
    grabador) llegan hechas: las de verdad salen de crear_app(); las pruebas pasan las suyas.
    arranque_windows(encendido) pone o quita el arranque con Windows (devuelve un texto de error o '').
    """

    def __init__(
        self,
        configuracion,
        *,
        cache,
        datos,
        cliente,
        cliente_lol,
        duelos,
        grabador=None,
        arranque_windows=sin_arranque_windows,
    ):
        self.configuracion = configuracion
        self.cfg = configuracion.valores
        self.grabador = grabador
        self.cache = cache
        self.datos = datos
        self.cliente = cliente
        self.lcu = cliente_lol
        self.duelos = duelos  # duelos de Master+ (lo llena el recolector)
        self.cola = Cola(al_fallar=self._fallo_tarea)
        self.recolector = None
        self.actualizador = actualizador.Actualizador(self)
        self._crear_piezas(arranque_windows)
        self.ultima_consulta = time.time()  # última vez que el panel pidió el estado
        self.al_mostrar = None  # lo pone la ventana principal: otra copia arrancada pide enseñarla
        self.al_salir = None  # lo ponen las ventanas: cierra la app del todo
        self.ventana_visible = None  # lo ponen las ventanas: ¿está la principal a la vista?
        self._resumen_duelos = (0.0, None)
        self._ventana_juego = (0.0, None)  # (cuándo se leyó, WindowMode del juego)
        self._arranco = False  # arrancar() ya se llamó (las pruebas usan la app sin arrancarla)

    def _crear_piezas(self, arranque_windows):
        """Las piezas de la app, cada una con lo que necesita de las demás."""
        configuracion, cache, datos, cliente, duelos = self.configuracion, self.cache, self.datos, self.cliente, self.duelos
        self.mis_cuentas = Cuentas(configuracion, cache, cliente, al_recuperar_clave=lambda: self.sesiones.reabrir())
        self.partidas = Partidas(cache, cliente, self.cuentas, self.cfg["inicio_temporada"])
        self.comparador = Comparador(self.cfg, duelos, cliente, datos, self.cuentas, self.partidas)
        self._ajustes = Ajustes(
            configuracion, datos, self.comparador, self.actualizador, arranque_windows, self._ajustes_guardados
        )
        self.revisor = Revisor(
            cache, cliente, datos, duelos, self.comparador, self.cuentas, self.partidas, en_partida=lambda: self.fase in EN_JUEGO
        )
        self.sesiones = Sesiones(
            lambda juego, yo, origen: Sesion(self, juego, yo, origen), cliente, self.mis_cuentas, self._partida_terminada
        )
        self._seleccion = Seleccion(self.lcu, datos, self.cuentas, self.partidas, self.comparador, self.notas_de)
        self.vigia = Vigia(
            self.lcu,
            cliente,
            configuracion,
            self.mis_cuentas,
            self.sesiones,
            self._seleccion,
            grabador=lambda: self.grabador,
            al_ver_cliente=self._al_ver_cliente,
        )

    # --- lo que llevan las piezas ---------------------------------------------------------------
    @property
    def cuentas(self):
        """Tus cuentas: puuid -> 'Nombre#TAG'."""
        return self.mis_cuentas.propias

    @property
    def error_clave(self):
        return self.mis_cuentas.error_clave

    @property
    def fase(self):
        return self.vigia.fase

    @property
    def modo(self):
        return self.vigia.modo

    @property
    def reloj(self):
        return self.vigia.reloj

    @property
    def cuenta_activa(self):
        return self.vigia.cuenta_activa

    @property
    def sesion(self):
        return self.sesiones.actual

    @property
    def seleccion(self):
        return self._seleccion.actual

    @property
    def sync(self):
        return self.partidas.sync

    @property
    def revisando(self):
        return self.revisor.revisando

    @property
    def ultima_revision(self):
        return self.revisor.ultima

    # --- arranque ---------------------------------------------------------------------
    def arrancar(self):
        self._arranco = True
        try:
            self.comprobar_clave()
        except ClaveInvalida as e:
            self.mis_cuentas.error_clave = str(e)
        except ErrorRiot as e:
            logger.warning("No se pudo comprobar la clave: %s", e)
        threading.Thread(target=self._bucle, args=(self.vigia.paso, 2.5), name="vigia", daemon=True).start()
        threading.Thread(target=self._bucle, args=(self._fondo, 20), name="fondo", daemon=True).start()
        # Con cuentas ya conocidas la región también lo es; si no (app recién instalada), el recolector
        # espera a que se abra el cliente y diga de qué región es.
        if self.cfg["cuentas"]:
            self._arrancar_recolector()
        self.actualizador.arrancar()
        if config.CONGELADA and self.cfg.get("siempre_en_marcha") and not inicio_windows.activo():
            inicio_windows.poner(True)

    def _al_ver_cliente(self):
        if self.recolector is None and self._arranco:
            self._arrancar_recolector()

    def _arrancar_recolector(self):
        if self.recolector or not self.cfg.get("recolectar", True):
            return
        # Tu región va con el cliente del panel (y su cuota); las demás, cada una con la suya.
        fuera = [(p, r) for p, r in rec.TODAS if r != self.cfg["region"]]
        self.recolector = rec.Recolector(
            self.duelos,
            config.leer_clave,
            self.datos.legendarios,
            pool=self.partidas.pool,
            mis_partidas=self.mis_partidas,
            mis_puuids=lambda: set(self.cuentas),
            cliente_europa=self.cliente,
            puede_europa=self._europa_libre,
            referencias=self.comparador.para_el_recolector,
            regiones=fuera,
        )
        if not self.recolector.arrancar():
            self.recolector = None

    def _europa_libre(self):
        """EUW comparte cuota con el panel: el recolector solo la usa con el cliente quieto."""
        return (
            not self.error_clave
            and self.fase not in PARTIDA_CERCA + EN_JUEGO
            and not self.sesiones.cargando()
            and self.sync["hechas"] >= self.sync["total"]
        )

    def _bucle(self, paso, pausa):
        while True:
            try:
                paso()
            except ClaveInvalida as e:
                self.mis_cuentas.error_clave = str(e)
            except ErrorRiot as e:
                logger.warning("%s", e)
            except Exception:  # el vigía y el bucle de fondo no pueden morir por un fallo suelto
                logger.exception("Fallo suelto en el hilo %s", threading.current_thread().name)
            time.sleep(pausa)

    def _fallo_tarea(self, e):
        if isinstance(e, ClaveInvalida):
            self.mis_cuentas.error_clave = str(e)
        elif isinstance(e, ErrorRiot):
            logger.warning("%s", e)
        else:
            logger.error("Tarea rota", exc_info=e)

    def _fondo(self):
        """El historial propio en segundo plano (sin estorbar a una partida que se está cargando)."""
        if self.error_clave or self.sesiones.cargando():
            return
        for puuid in list(self.cuentas):
            self.partidas.sincronizar(puuid, ocupada=self.sesiones.cargando)
        if self.cuentas and self.fase not in EN_JUEGO:
            self.revisor.rellenar()

    def _partida_terminada(self, s):
        """Tu partida ha acabado: si era en la Grieta, se prepara su revisión (con la grabación, si la hay)."""
        if s.mapa != GRIETA or not self.cfg.get("revisar", True):
            return
        panel = s.panel()
        carpeta = self.grabador.carpeta_reciente() if self.grabador else None
        self.revisor.en_segundo_plano(s.id, s.yo, panel, carpeta)

    def _ajustes_guardados(self, nuevo):
        self.comparador.olvidar()
        if "grabar" in nuevo:
            self.grabador = (self.grabador or Grabador(self.cfg)) if nuevo["grabar"] else None
        for rid in nuevo.get("cuentas", []):
            threading.Thread(target=self.mis_cuentas.apuntar, args=(rid,), daemon=True).start()
        if self.sesion:
            self.sesion.invalidar_panel()  # las notas y las reglas nuevas salen ya en el panel

    # --- lo que piden el panel y las sesiones -------------------------------------------------------
    def comprobar_clave(self):
        self.mis_cuentas.comprobar_clave()

    def poner_clave(self, clave):
        return self.mis_cuentas.poner_clave(clave)

    def buscar(self, rid):
        return self.sesiones.buscar(rid)

    def volver(self):
        return self.sesiones.volver()

    def actualizar_modo(self):
        self.vigia.actualizar_modo()

    def duelo(self, a, pos, b):
        return self.comparador.duelo(a, pos, b)

    def pool_contra(self, pos, rival, cola=None):
        return self.comparador.pool_contra(pos, rival, cola)

    def mis_partidas(self, cola=None):
        return self.partidas.mis_partidas(cola)

    def traer_partida(self, id_, cancelada=None, fondo=False):
        return self.partidas.traer_partida(id_, cancelada, fondo)

    def traer_linea(self, id_, cancelada=None):
        return self.partidas.traer_linea(id_, cancelada)

    def notas_de(self, campeones, rivales=()):
        return self._ajustes.notas_de(campeones, rivales)

    def ajustes(self):
        return self._ajustes.leer()

    def guardar_ajustes(self, cambios):
        return self._ajustes.guardar(cambios)

    def revisiones(self):
        return self.revisor.lista()

    def revision(self, id_):
        return self.revisor.una(id_)

    def abrir_carpeta(self, id_):
        return self.revisor.abrir_carpeta(id_)

    def abrir_clip(self, id_, i):
        return self.revisor.abrir_clip(id_, i)

    def salir(self):
        """Cierra la app del todo (con 'siempre en marcha' no se cierra sola)."""
        if not self.al_salir:
            return {"ok": False, "error": "Sin ventanas no puedo cerrarme desde aquí."}
        threading.Timer(0.5, self.al_salir).start()
        return {"ok": True}

    # --- estado para el panel ------------------------------------------------------------------------
    def _para_el_modo(self, panel):
        """Con el juego ya empezado, solo datos: fuera el plan y los veredictos de línea.

        Riot no permite que una app saque conclusiones por el jugador durante la partida; antes de empezar
        (selección y pantalla de carga) sí se pueden enseñar.
        """
        if self.modo != "juego":
            return panel
        # Los colores de alerta también son una lectura: en juego todo va en neutro.
        jungla = panel.get("jungla")
        if jungla:
            # El mapa de dónde suele estar en los primeros minutos se queda fuera: ya jugando, se parecería a seguirle.
            jungla = dict(jungla, tarjetas=[dict(t, tono="neutro") for t in jungla["tarjetas"]], mapa={})
        return dict(
            panel,
            plan=[],
            lineas=[dict(l, veredicto="", tono="neutro") for l in panel["lineas"]],
            avisos=[dict(a, tono="neutro") for a in panel["avisos"]],
            jungla=jungla,
            duelo=None,  # lo que hacen los que ganan el duelo es una lectura: solo antes de empezar
        )

    def _estado_overlay(self):
        if not self.cfg.get("overlay", True):
            return {"activo": False, "atajo": "", "aviso": ""}
        leido, modo = self._ventana_juego
        if time.time() - leido > 30:
            modo = modo_ventana(self.lcu.ruta)
            self._ventana_juego = (time.time(), modo)
        aviso = ""
        if modo is not None and modo != MODO_SIN_BORDES:
            aviso = (
                "El juego no está en ventana sin bordes: el panel no puede salir encima. "
                "Cámbialo en Opciones > Vídeo > Modo de ventana."
            )
        return {"activo": True, "atajo": self.cfg.get("atajo_overlay", ""), "aviso": aviso}

    def _estado_recolector(self):
        if time.time() - self._resumen_duelos[0] > 30:
            r = self.duelos.resumen()
            r["activo"] = bool(self.recolector)
            r["pool"] = [{"campeon": self.datos.nombre(c), "pos": an.NOMBRE_POS.get(p, p)} for c, p in self.partidas.pool()]
            self._resumen_duelos = (time.time(), r)
        return self._resumen_duelos[1]

    def estado(self, contar=True):
        # El overlay también pide el estado, pero estar escondido encima del juego no es "mirar el panel".
        if contar:
            self.ultima_consulta = time.time()
        s = self.sesion
        limitador = self.cliente.limitador
        return {
            "fase": self.fase,
            "fase_txt": FASES.get(self.fase, self.fase) if self.fase else "Cliente del LoL cerrado",
            "modo": self.modo,
            "reloj": self.reloj,
            "overlay": self._estado_overlay(),
            "cuenta": self.cuentas.get(self.cuenta_activa, ""),
            "clave": {"ok": not self.error_clave, "error": self.error_clave},
            "cuota": limitador.estado(self.cliente.region),
            "sync": self.sync,
            "grabacion": self.grabador.estado() if self.grabador else None,
            "ultima_revision": self.ultima_revision,
            "seleccion": self.seleccion,
            "recolector": self._estado_recolector(),
            "version": self.actualizador.estado,
            "novedades": self.actualizador.novedades(),
            "panel": self._para_el_modo(s.panel()) if s else None,
        }


def crear_app(configuracion=None, *, cliente=None, cliente_lol=None, duelos=None, grabar=True):
    """La app de verdad: config.json, cache.db y duelos.db de la carpeta de datos, la API de Riot y el cliente del LoL.

    Las herramientas pueden cambiar alguna pieza. Con una configuración propia (p. ej. Configuracion.en_memoria) no se
    escribe config.json ni se toca el arranque con Windows. grabar=False: sin grabación aunque la configuración la pida.
    """
    arranque_windows = inicio_windows.poner if configuracion is None else sin_arranque_windows
    configuracion = configuracion or config.Configuracion.de_archivo()
    cfg = configuracion.valores
    cache = Cache(config.RUTA_CACHE)
    return App(
        configuracion,
        cache=cache,
        datos=Datos(cache),
        cliente=cliente or Cliente(cfg, config.leer_clave),
        cliente_lol=cliente_lol or lcu.Cliente(cfg["ruta_lol"]),
        duelos=duelos or BaseDuelos(),
        grabador=Grabador(cfg) if grabar and cfg.get("grabar") else None,
        arranque_windows=arranque_windows,
    )
