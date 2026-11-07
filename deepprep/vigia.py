"""Vigila el cliente del LoL y decide qué partida enseña el panel: una sesión por partida."""

import logging
import threading
import time
from collections.abc import Callable

from .config import Configuracion
from .constantes import GRIETA
from .cuentas import Cuentas
from .grabacion import Grabador
from .lcu import Cliente as ClienteLoL
from .riot import REGION_DE, ClaveInvalida, Cliente, ErrorRiot
from .seleccion import Seleccion
from .sesion import Sesion
from .tipos import Json, Resultado

logger = logging.getLogger(__name__)

FASES = {
    "None": "Cliente abierto",
    "Lobby": "En sala",
    "Matchmaking": "En cola",
    "ReadyCheck": "Partida encontrada",
    "ChampSelect": "Selección de campeón",
    "GameStart": "Empezando partida",
    "InProgress": "En partida",
    "Reconnect": "Reconectando",
    "WaitingForStats": "Fin de partida",
    "PreEndOfGame": "Fin de partida",
    "EndOfGame": "Fin de partida",
}
EN_JUEGO = ("GameStart", "InProgress", "Reconnect")
# Fases en las que la partida está al caer: el historial propio deja de descargarse.
PARTIDA_CERCA = ("Matchmaking", "ReadyCheck", "ChampSelect", "GameStart")
# Cada cuánto se pregunta a Riot por tu partida en vivo: sin cliente a la vista y ya en partida.
SONDEO_SIN_CLIENTE_S = 45
SONDEO_EN_PARTIDA_S = 5
# En la pantalla de carga la API del juego ya contesta, con el reloj parado en 0-1 s. La partida ha empezado cuando
# el reloj avanza (AVANCE_S desde la primera lectura) o si ya va por EMPEZADA_S (la app se abre a media partida).
RELOJ_AVANCE_S = 0.5
RELOJ_EMPEZADA_S = 3.0
# Cuánto de la ventana de 2 minutos de cuota pueden gastar las tareas de fondo según cómo esté el cliente.
FONDO_SIN_CLIENTE, FONDO_PARTIDA_CERCA, FONDO_NORMAL = 40, 0, 85


class Sesiones:
    """La sesión que enseña el panel (actual): la de tu partida o la de alguien buscado a mano.

    Una búsqueda a mano queda fijada: no se pisa con la tuya hasta que empiece tu siguiente partida.
    crear(juego, yo, origen) hace la sesión; al_terminar(sesion) se llama cuando tu partida acaba.
    """

    def __init__(
        self, crear: Callable[[Json, str, str], Sesion], cliente: Cliente, cuentas: Cuentas, al_terminar: Callable[[Sesion], None]
    ) -> None:
        self._crear = crear
        self.cliente = cliente
        self.cuentas = cuentas
        self._al_terminar = al_terminar
        self.actual: Sesion | None = None
        self.fijada = False  # el usuario ha buscado otra partida a mano y no hay que pisársela
        self._ultimo_juego: tuple[Json, str, str] | None = None  # (juego, yo, origen) de la última que se abrió
        self._lock = threading.RLock()

    def abrir(self, juego: Json, yo: str, origen: str, forzar: bool = False) -> None:
        with self._lock:
            s = self.actual
            if s and not forzar and s.id == juego.get("gameId") and s.yo == yo:
                s.terminada = False
                return
            if s:
                s.cancelar()
            self._ultimo_juego = (juego, yo, origen)
            # Se lanza antes de publicarla: así nadie pide su panel mientras se tiene este cerrojo.
            nueva = self._crear(juego, yo, origen)
            nueva.lanzar()
            self.actual = nueva

    def reabrir(self) -> None:
        """La clave vuelve a valer: la partida que se estaba viendo se pide otra vez entera."""
        if self._ultimo_juego and self.actual and not self.actual.terminada:
            juego, yo, origen = self._ultimo_juego
            self.abrir(juego, yo, origen, forzar=True)

    def terminar(self) -> None:
        """La partida propia ha acabado: el panel se queda a la vista y se prepara la revisión."""
        s = self.actual
        if not s or s.origen != "propia" or s.terminada:
            return
        s.terminada = True
        self._al_terminar(s)

    def cargando(self) -> bool:
        s = self.actual
        return bool(s and not s.terminada and s.hechas < s.total)

    def buscar(self, rid: str) -> Resultado:
        """Abre a mano la partida en vivo de cualquier jugador."""
        try:
            r = self.cuentas.resolver(rid.strip())
            if not r:
                return {"ok": False, "error": "No encuentro esa cuenta. Formato: Nombre#TAG"}
            juego = self.cliente.partida_activa(r[0])
        except ClaveInvalida as e:
            self.cuentas.error_clave = str(e)
            return {"ok": False, "error": str(e)}
        except ErrorRiot as e:
            return {"ok": False, "error": str(e)}
        if not juego:
            return {"ok": False, "error": f"{r[1]} no está en partida ahora mismo."}
        self.fijada = True
        self.abrir(juego, r[0], "propia" if r[0] in self.cuentas.propias else "manual")
        return {"ok": True}

    def volver(self) -> Resultado:
        """Deja de mostrar la partida buscada a mano."""
        with self._lock:
            self.fijada = False
            if self.actual and self.actual.origen == "manual":
                self.actual.cancelar()
                self.actual = None
        return {"ok": True}


class Vigia:
    """Mira el cliente del LoL (cada 2,5 s): fase, cuenta abierta, región y si empieza o acaba tu partida.

    grabador() da el grabador de ahora (None sin grabación). al_ver_cliente() se llama la primera vez que se ve el
    cliente abierto (ya se sabe su región).
    """

    def __init__(
        self,
        lcu: ClienteLoL,
        cliente: Cliente,
        configuracion: Configuracion,
        cuentas: Cuentas,
        sesiones: Sesiones,
        seleccion: Seleccion,
        grabador: Callable[[], Grabador | None],
        al_ver_cliente: Callable[[], None],
    ) -> None:
        self.lcu = lcu
        self.cliente = cliente
        self.configuracion = configuracion
        self.cfg = configuracion.valores
        self.cuentas = cuentas
        self.sesiones = sesiones
        self.seleccion = seleccion
        self._grabador = grabador
        self._al_ver_cliente = al_ver_cliente
        self.fase: str | None = None  # None = cliente cerrado
        # 'previa' (fuera de partida o en selección), 'carga' (pantalla de carga) o 'juego' (ya se juega).
        # En 'juego' el panel solo enseña datos: Riot no permite sacar conclusiones durante la partida.
        self.modo = "previa"
        self.reloj: float | None = None  # segundos de partida según el propio juego (None hasta que empieza)
        self._reloj_en_carga: float | None = None  # la primera lectura del reloj en la pantalla de carga
        self.cuenta_activa: str | None = None  # puuid de la cuenta abierta en el cliente
        self.ultimo_sondeo = 0.0  # última vez que se preguntó a Riot por la partida en vivo
        self._plataforma_vista = False  # región del cliente ya mirada en esta sesión del cliente

    def paso(self) -> None:
        ahora = time.time()
        if self.cuentas.error_clave and not self.cuentas.reprobar_clave(ahora):
            return
        est = self.lcu.estado()
        if not est:
            self._sin_cliente(ahora)
            return
        if not self._plataforma_vista:
            self._plataforma_vista = True
            self.ajustar_plataforma(self.lcu.plataforma())
            self._al_ver_cliente()
        anterior, self.fase = self.fase, est["fase"]
        self.cliente.limitador.tope_fondo = FONDO_PARTIDA_CERCA if self.fase in PARTIDA_CERCA else FONDO_NORMAL
        if est["nombre"] and est["tag"]:
            self.cuenta_activa = self.cuentas.apuntar(f"{est['nombre']}#{est['tag']}", recordar=True) or self.cuenta_activa
        if self.fase == "ChampSelect":
            self.seleccion.leer()
        else:
            self.seleccion.cerrar()
        self.actualizar_modo()
        if self.fase in EN_JUEGO:
            self._en_partida(anterior, ahora)
        else:
            self.sesiones.terminar()

    def _sin_cliente(self, ahora: float) -> None:
        """Cliente cerrado: todo a cero y, de vez en cuando, se pregunta a Riot si alguna cuenta tuya está en partida
        (p. ej. con el LoL instalado en otra ruta)."""
        self._plataforma_vista = False
        self.fase = None
        self.seleccion.cerrar()
        self.actualizar_modo()
        self.cliente.limitador.tope_fondo = FONDO_SIN_CLIENTE
        if self.sesiones.fijada or ahora - self.ultimo_sondeo < SONDEO_SIN_CLIENTE_S:
            return
        self.ultimo_sondeo = ahora
        for puuid in list(self.cuentas.propias):
            juego = self.cliente.partida_activa(puuid)
            if juego:
                self.sesiones.abrir(juego, puuid, "propia")
                return
        self.sesiones.terminar()

    def _en_partida(self, anterior: str | None, ahora: float) -> None:
        """Ya en partida: al empezar se arma el grabador, y tu sesión se abre en cuanto Riot da la partida en vivo."""
        if anterior not in EN_JUEGO:
            self.sesiones.fijada = False  # partida nueva: manda la propia
            # Si no se sabe el mapa se graba igual: mejor una grabación de más que una de menos.
            grabador = self._grabador()
            if grabador and self.lcu.mapa() in (0, GRIETA):
                grabador.armar()
        s = self.sesiones.actual
        viva = s and s.origen == "propia" and not s.terminada
        if viva or self.sesiones.fijada or not self.cuenta_activa or ahora - self.ultimo_sondeo < SONDEO_EN_PARTIDA_S:
            return
        self.ultimo_sondeo = ahora
        juego = self.cliente.partida_activa(self.cuenta_activa)
        if juego:
            self.sesiones.abrir(juego, self.cuenta_activa, "propia")

    def ajustar_plataforma(self, plataforma: str | None) -> None:
        """La región de la API sale del cliente del LoL (para quien no juega en EUW)."""
        if not plataforma or plataforma == self.cfg.get("plataforma"):
            return
        region = REGION_DE.get(plataforma)
        if not region:
            return
        logger.info("El cliente es de %s: uso esa región", plataforma)
        self.cfg.update(plataforma=plataforma, region=region)
        self.configuracion.guardar()
        self.cliente.poner_plataforma(plataforma, region)

    def actualizar_modo(self) -> None:
        """Pantalla de carga o juego empezado, según el reloj del propio juego (el overlay lo llama más a menudo).

        Que el reloj conteste no basta: en la pantalla de carga ya contesta, parado (RELOJ_AVANCE_S). Una vez
        empezada, la partida no vuelve a 'carga' aunque el reloj falle un momento o se pare en una pausa: la vista
        de carga lleva conclusiones (plan, duelo) que Riot no deja enseñar durante la partida.
        """
        if self.fase not in EN_JUEGO:
            self.modo, self.reloj, self._reloj_en_carga = "previa", None, None
            return
        lectura = self.lcu.reloj()
        if self.modo != "juego" and lectura is not None:
            if self._reloj_en_carga is None:
                self._reloj_en_carga = lectura
            if lectura >= RELOJ_EMPEZADA_S or lectura - self._reloj_en_carga >= RELOJ_AVANCE_S:
                self.modo = "juego"
        if self.modo != "juego":
            self.modo, self.reloj = "carga", None
        elif lectura is not None:
            self.reloj = lectura
