"""Arranque: py -m deepprep  (--sin-ventana: sin ventanas, solo lo de fondo: vigía, grabación y recolector)

--demo: la app con una partida de ejemplo, sin el LoL ni clave de Riot (ver deepprep/demo). --escena seleccion|carga|juego
elige con qué empieza y --puerto N pone su canal de control en ese puerto (si no, en uno libre).
"""

import json
import logging
import sys
import threading
import time
from types import ModuleType
from typing import TYPE_CHECKING

from . import config
from .sistema import pedir_a_la_copia_en_marcha

if TYPE_CHECKING:
    from .app import App
    from .servidor import Servidor
    from .tipos import AppDelPanel

logger = logging.getLogger(__name__)

# Sin ventanas (--sin-ventana, o si la interfaz no arranca): sin nadie mirando el estado durante este tiempo la app se
# cierra sola, salvo con el cliente del LoL abierto, porque tiene que seguir ahí para grabar la siguiente partida.
MINUTOS_SIN_PANEL = 5


def pedir_que_se_muestre(url: str) -> bool:
    """Ya hay otra copia en marcha: que enseñe su ventana. Devuelve False si no sabe hacerlo."""
    try:
        return bool(json.loads(pedir_a_la_copia_en_marcha(url, "api/mostrar")).get("ok"))
    except (OSError, ValueError):
        return False


def opcion(nombre: str) -> str | None:
    """El valor que sigue a una opción de la línea de órdenes (--puerto 5252), o None."""
    i = sys.argv.index(nombre) if nombre in sys.argv else -1
    return sys.argv[i + 1] if 0 <= i < len(sys.argv) - 1 else None


def main() -> None:
    if "--grabar" in sys.argv:
        _grabar()
        return
    config.configurar_registro()
    if "--demo" in sys.argv:
        _demo()
        return
    for aviso in config.AVISOS:  # la mudanza de los datos de Porofesor, si la ha habido
        logger.info("%s", aviso)

    from . import actualizador

    if "--actualizar" in sys.argv:
        _terminar_actualizacion(actualizador)
        return
    # App empaquetada abierta desde la carpeta descomprimida: se instala y arranca la copia instalada.
    if actualizador.instalar_si_hace_falta():
        return
    cfg = config.cargar()
    url = f"http://127.0.0.1:{cfg['puerto']}/"
    con_ventana = cfg.get("abrir_ventana", True) and "--sin-ventana" not in sys.argv

    from . import servidor
    from .app import crear_app

    app = crear_app()
    try:
        srv = servidor.crear(app, cfg["puerto"])
    except OSError:
        # El puerto está ocupado: ya hay otra copia en marcha, basta con que enseñe su ventana
        # (salvo si esta es la del arranque con Windows, que no tiene que enseñar nada).
        if "--oculta" not in sys.argv and con_ventana and not pedir_que_se_muestre(url):
            logger.warning("Ya hay una copia en %s, pero no contesta: no abro otra", url)
        return
    app.arrancar()
    threading.Thread(target=srv.serve_forever, name="servidor", daemon=True).start()
    logger.info("Deep Prep en %s", url)
    if con_ventana and _ventanas(app):
        return
    _seguir_mientras_haga_falta(app)


def _grabar() -> None:
    """Proceso aparte que graba una partida (lo lanza la app al empezar cada partida en la Grieta)."""
    from . import grabacion

    prueba = int(sys.argv[sys.argv.index("--prueba") + 1]) if "--prueba" in sys.argv else 0
    grabacion.grabar(config.cargar(), prueba_seg=prueba)


def _terminar_actualizacion(actualizador: ModuleType) -> None:
    """Versión nueva recién descargada: espera a que se cierre la vieja y se instala encima."""
    i = sys.argv.index("--actualizar")
    modo = sys.argv[i + 3] if len(sys.argv) > i + 3 else None  # la 1.0.0 y la 1.0.1 no lo pasan
    actualizador.terminar_actualizacion(sys.argv[i + 1], sys.argv[i + 2], modo)


def _ventanas(app: "AppDelPanel", demo: bool = False) -> bool:
    """Abre las ventanas (bloquea hasta que la app se cierra) y devuelve True.

    Si la interfaz no arranca (le falta algo a Qt en el paquete, por ejemplo), lo apunta en el registro y devuelve
    False: la app sigue sin ventanas, grabando y recogiendo duelos. demo: la ventana de la demo, sin overlay encima del
    juego; se cierra de verdad al cerrarla.
    """
    try:
        import ctypes

        # Así la barra de tareas usa el icono de Deep Prep y no el de Python.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Samuel.DeepPrep")
        from .nativa.ventanas import VentanasQt

        titulo = "Deep Prep · demo" if demo else "Deep Prep"
        VentanasQt(app, titulo=titulo, demo=demo).arrancar(oculta="--oculta" in sys.argv and not demo)
        return True
    except Exception:  # cualquier fallo de Qt: mejor sin ventanas que sin grabar ni recoger
        logger.exception("La interfaz no ha podido arrancar; sigo sin ventanas")
        return False


def _seguir_mientras_haga_falta(app: "App") -> None:
    """Sin ventanas, la app sigue mientras alguien lea su estado, el cliente del LoL esté abierto o esté 'siempre en
    marcha'."""
    try:
        while (
            app.cfg.get("siempre_en_marcha") or time.time() - app.ultima_consulta < MINUTOS_SIN_PANEL * 60 or app.fase is not None
        ):
            time.sleep(5)
        logger.info("Nadie mira y el cliente está cerrado; cierro.")
    except KeyboardInterrupt:
        pass


def _demo() -> None:
    """La demo (--demo): la ventana de siempre con la partida de ejemplo de deepprep/demo.

    Sin vigía del cliente del LoL, sin llamadas a Riot, sin grabación, recolector ni actualizaciones, sin instalarse
    ni tocar accesos directos o el arranque con Windows. config.DATOS es una carpeta temporal nueva (la elige config al
    ver --demo) y se borra al salir: al cerrar la ventana, desde Ajustes o con /api/salir de su canal de control.
    """
    from . import demo, servidor

    app = demo.AppDemo(config.DATOS, escena=opcion("--escena") or demo.ESCENA_INICIAL)
    try:
        srv = servidor.crear(app, int(opcion("--puerto") or 0))
    except (OSError, ValueError) as e:
        logger.error("La demo no puede abrir su canal de control: %r", e)
        _cerrar_demo(None)
        return
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    threading.Thread(target=srv.serve_forever, name="servidor", daemon=True).start()
    logger.info("Deep Prep (demo) en %s; lo que guardes va a %s y se borra al salir", url, config.DATOS)
    try:
        _ventanas(app, demo=True)
    except KeyboardInterrupt:
        pass
    finally:
        _cerrar_demo(srv)


def _cerrar_demo(srv: "Servidor | None") -> None:
    from . import demo

    if srv:
        srv.shutdown()
        srv.server_close()
    logger.info("Demo cerrada; borro %s", config.DATOS)
    config.cerrar_registro()
    demo.borrar_carpeta(config.DATOS)


if __name__ == "__main__":
    main()
