"""Arranque: py -m deepprep  (--sin-ventana: solo el servidor, sin ventanas)"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import config
from .sistema import pedir_a_la_copia_en_marcha

logger = logging.getLogger(__name__)

# Sin ventanas (--sin-ventana o sin pywebview): sin panel abierto durante este tiempo la app se cierra sola,
# salvo con el cliente del LoL abierto, porque tiene que seguir ahí para grabar la siguiente partida.
MINUTOS_SIN_PANEL = 5


def abrir_ventana(url):
    """Plan B sin pywebview: el panel como ventana propia de Chrome o Edge, o en el navegador por defecto."""
    candidatos = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for exe in candidatos:
        if exe.is_file():
            subprocess.Popen([str(exe), f"--app={url}", "--window-size=1500,950"])
            return
    webbrowser.open(url)


def pedir_que_se_muestre(url):
    """Ya hay otra copia en marcha: que enseñe su ventana. Devuelve False si no sabe hacerlo."""
    try:
        return bool(json.loads(pedir_a_la_copia_en_marcha(url, "api/mostrar")).get("ok"))
    except (OSError, ValueError):
        return False


def main():
    if "--grabar" in sys.argv:
        _grabar()
        return
    config.configurar_registro()
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
        # El puerto está ocupado: ya hay otra copia en marcha, basta con enseñar su panel
        # (salvo si esta es la del arranque con Windows, que no tiene que enseñar nada).
        if "--oculta" not in sys.argv and con_ventana and not pedir_que_se_muestre(url):
            abrir_ventana(url)
        return
    app.arrancar()
    threading.Thread(target=srv.serve_forever, name="servidor", daemon=True).start()
    logger.info("Deep Prep en %s", url)
    if con_ventana and _ventanas(app, url):
        return
    _seguir_mientras_haga_falta(app)


def _grabar():
    """Proceso aparte que graba una partida (lo lanza la app al empezar cada partida en la Grieta)."""
    from . import grabacion

    prueba = int(sys.argv[sys.argv.index("--prueba") + 1]) if "--prueba" in sys.argv else 0
    grabacion.grabar(config.cargar(), prueba_seg=prueba)


def _terminar_actualizacion(actualizador):
    """Versión nueva recién descargada: espera a que se cierre la vieja y se instala encima."""
    i = sys.argv.index("--actualizar")
    modo = sys.argv[i + 3] if len(sys.argv) > i + 3 else None  # la 1.0.0 y la 1.0.1 no lo pasan
    actualizador.terminar_actualizacion(sys.argv[i + 1], sys.argv[i + 2], modo)


def _ventanas(app, url):
    """Abre las ventanas propias (bloquea hasta que la app se cierra) y devuelve True.

    Sin pywebview, sin WebView2 o con un fallo de .NET abre el panel en el navegador y devuelve False: no hay overlay.
    """
    try:
        import ctypes

        # Así la barra de tareas usa el icono de Deep Prep y no el de Python.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Samuel.DeepPrep")
        from .ventanas import Ventanas

        Ventanas(app, url).arrancar(oculta="--oculta" in sys.argv)
        return True
    except Exception as e:  # noqa: BLE001  sin pywebview, sin WebView2 o un fallo de .NET: panel en Chrome, sin overlay
        logger.warning("Sin ventanas propias (%r); abro el panel en el navegador y no habrá overlay", e)
        abrir_ventana(url)
        return False


def _seguir_mientras_haga_falta(app):
    """Sin ventanas propias, la app sigue mientras alguien mire el panel, el cliente del LoL esté abierto o esté
    'siempre en marcha'."""
    try:
        while (
            app.cfg.get("siempre_en_marcha") or time.time() - app.ultima_consulta < MINUTOS_SIN_PANEL * 60 or app.fase is not None
        ):
            time.sleep(5)
        logger.info("Nadie mira el panel y el cliente está cerrado; cierro.")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
