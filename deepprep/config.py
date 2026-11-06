"""Rutas del proyecto y configuración editable (config.json).

Los datos de cada usuario (clave, configuración, cachés, registros) van en DATOS: en la app empaquetada,
%LOCALAPPDATA%\\DeepPrep, para que una actualización del programa no los toque; desde el código, la
carpeta del proyecto. DEEPPREP_DATOS los manda a otra carpeta (para probar sin tocar los de verdad);
POROFESOR_DATOS, el nombre de antes, también vale.

Hasta la 1.0.2 la app se llamaba Porofesor y guardaba los datos en %LOCALAPPDATA%\\Porofesor: la copia
instalada los muda a la carpeta nueva al arrancar, antes de que nada abra las bases de datos o el registro.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

CONGELADA = getattr(sys, "frozen", False)  # app empaquetada (PyInstaller)
RAIZ = Path(sys.executable).parent if CONGELADA else Path(__file__).resolve().parent.parent
# Dónde se instala la app empaquetada (lo usa actualizador.py). DEEPPREP_PROGRAMA la manda a otra carpeta.
PROGRAMA = Path(os.environ.get("DEEPPREP_PROGRAMA") or os.environ.get("POROFESOR_PROGRAMA")
                or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "DeepPrep")
# Lo que pasa al mudar los datos de Porofesor. Aún no hay registro abierto: __main__ lo apunta al abrirlo.
AVISOS = []


def falta_mudar(viejos, nuevos):
    """¿Hay datos de Porofesor que aún no se han pasado a la carpeta de Deep Prep?"""
    return viejos.is_dir() and not (nuevos / "config.json").exists()


def mudar_datos(viejos, nuevos, intentos=30, pausa=0.5):
    """Pasa los datos de Porofesor (viejos) a la carpeta de Deep Prep (nuevos). Devuelve la carpeta que hay que usar.

    En la misma unidad basta con cambiarle el nombre a la carpeta. Si Windows no deja (algo tiene un archivo abierto:
    la versión que acaba de instalar esta aún cerrándose, el antivirus...), se reintenta un rato y luego se copia,
    dejando la vieja como estaba. config.json se copia el último: hasta que está, la mudanza no cuenta como hecha y
    se repite en el siguiente arranque. Si tampoco se puede copiar, esta vez se sigue con la carpeta vieja.
    """
    if not falta_mudar(viejos, nuevos):
        return nuevos
    # La descarga con la que se instaló esta versión: ya no sirve y no hace falta mudarla.
    shutil.rmtree(viejos / "actualizacion", ignore_errors=True)
    try:
        nuevos.rmdir()  # si existe sin config.json y vacía, fuera, para poder cambiarle el nombre a la vieja
    except OSError:
        pass
    error = None
    for _ in range(intentos):
        try:
            os.rename(viejos, nuevos)
            AVISOS.append(f"Datos de Porofesor movidos de {viejos} a {nuevos}")
            return nuevos
        except OSError as e:
            error = e
            if nuevos.exists() or not viejos.is_dir():  # ya hay algo en la nueva, u otra copia acaba de mudarlos
                break
            time.sleep(pausa)
    if not falta_mudar(viejos, nuevos):
        return nuevos

    def sobrante(carpeta, nombres):
        # Los cerrojos se rehacen solos; config.json va aparte, al final.
        fuera = {n for n in nombres if n.lower().endswith(".lock")}
        if Path(carpeta) == viejos:
            fuera |= {n for n in nombres if n.lower() in ("actualizacion", "config.json")}
        return fuera

    try:
        shutil.copytree(viejos, nuevos, ignore=sobrante, dirs_exist_ok=True)
        if (viejos / "config.json").is_file():
            shutil.copy2(viejos / "config.json", nuevos / "config.json")
    except OSError as e:
        AVISOS.append(f"No se pudieron pasar los datos de {viejos} a {nuevos} ({e!r}); sigo con los de {viejos}")
        return viejos
    AVISOS.append(f"Datos de Porofesor copiados de {viejos} a {nuevos} (no se pudieron mover: {error!r}); la carpeta vieja se queda")
    return nuevos


def elegir_datos(entorno=None, argv=None):
    """La carpeta de datos de este proceso; si toca, antes muda ahí los de Porofesor."""
    entorno = os.environ if entorno is None else entorno
    argv = sys.argv if argv is None else argv
    propia = entorno.get("DEEPPREP_DATOS") or entorno.get("POROFESOR_DATOS")
    if propia:
        return Path(propia)
    if not CONGELADA:
        return RAIZ
    local = Path(entorno.get("LOCALAPPDATA", Path.home()))
    viejos, nuevos = local / "Porofesor", local / "DeepPrep"
    if not falta_mudar(viejos, nuevos):
        return nuevos
    # Solo muda los datos la copia instalada al arrancar. La que instala una actualización pedida por una 1.0.x
    # corre desde dentro de la carpeta vieja (la descarga va ahí) y la recién descomprimida puede tener aún abierta
    # la versión vieja: las dos siguen con la carpeta vieja (y su config.json, sin crear uno vacío en la nueva).
    # El proceso que graba tampoco: lo lanza la app ya en marcha, que tiene abiertos los datos.
    if RAIZ.resolve() != PROGRAMA.resolve() or "--actualizar" in argv or "--grabar" in argv:
        return viejos
    return mudar_datos(viejos, nuevos)


DATOS = elegir_datos()
DATOS.mkdir(parents=True, exist_ok=True)
RUTA_CLAVE = DATOS / "clave.txt"
RUTA_CONFIG = DATOS / "config.json"
RUTA_CACHE = DATOS / "cache.db"
RUTA_WEB = Path(__file__).resolve().parent / "web"

POR_DEFECTO = {
    # Cuentas propias. La que esté abierta en el cliente del LoL se añade sola.
    "cuentas": [],
    "plataforma": "euw1",
    "region": "europe",
    "puerto": 5151,
    # Partidas recientes que se miran de cada jugador (las 5 primeras llegan en segundos).
    "partidas_por_jugador": 20,
    # Líneas de tiempo: son las consultas caras, por eso van contadas.
    "lineas_jungla_rival": 8,
    "lineas_por_jugador": 4,
    "inicio_temporada": "2026-01-01",
    # Dónde está instalado el LoL. Si ahí no está, se busca solo (ajustes de Riot y discos habituales).
    "ruta_lol": "C:/Riot Games/League of Legends",
    "abrir_ventana": True,
    # Graba la pantalla de cada partida en la Grieta (queda en Vídeos/LoL-coach) para revisarla después.
    "grabar": True,
    # "auto": con la gráfica si se puede (NVIDIA, AMD o Intel); "cpu": siempre con el procesador.
    "grabacion_codificador": "auto",
    # Al pasar de estos GB, se borran las partidas grabadas más viejas (0 = no borrar nunca).
    "grabacion_max_gb": 50,
    # Panel encima del juego: sale solo en la pantalla de carga y, ya jugando, mientras se mantiene el atajo.
    # Solo funciona con el juego en ventana sin bordes.
    "overlay": True,
    "atajo_overlay": "ctrl+tab",
    "overlay_opacidad": 0.94,
    # Tus notas por campeón (id -> texto): salen cuando ese campeón está en tu partida.
    "notas": {},
    # Siempre en marcha: arranca con Windows (con la ventana escondida) y no se cierra al cerrar el LoL,
    # para que el recolector de duelos siga llenando la base.
    "siempre_en_marcha": True,
    # Con quién se comparan tus números en el duelo y en la revisión: "perfil" (el jugador de perfil_base),
    # "ganan" (los Master+ que ganan ese duelo), "challenger", "gm" (Gran Maestro o más) o "mis_victorias".
    # Las referencias por campeón (id -> Nombre#TAG) mandan sobre esto cuando juegas ese campeón.
    "comparar_con": "ganan",
    "perfil_base": "",
    "referencias": {},
    # Revisión automática al acabar cada partida propia en la Grieta.
    "revisar": True,
    "recordatorios": [],
}


def cargar():
    cfg = dict(POR_DEFECTO)
    if RUTA_CONFIG.exists():
        try:
            cfg.update(json.loads(RUTA_CONFIG.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            print(f"config.json no se pudo leer ({e}); uso los valores por defecto")
    else:
        RUTA_CONFIG.write_text(json.dumps(POR_DEFECTO, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def guardar(cfg):
    RUTA_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def leer_clave():
    try:
        return RUTA_CLAVE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def guardar_clave(clave):
    RUTA_CLAVE.write_text(clave.strip(), encoding="utf-8")
