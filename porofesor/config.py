"""Rutas del proyecto y configuración editable (config.json).

Los datos de cada usuario (clave, configuración, cachés, registros) van en DATOS: en la app empaquetada,
%LOCALAPPDATA%\\Porofesor, para que una actualización del programa no los toque; desde el código, la
carpeta del proyecto. POROFESOR_DATOS los manda a otra carpeta (para probar sin tocar los de verdad).
"""
import json
import os
import sys
from pathlib import Path

CONGELADA = getattr(sys, "frozen", False)  # app empaquetada (PyInstaller)
RAIZ = Path(sys.executable).parent if CONGELADA else Path(__file__).resolve().parent.parent
if os.environ.get("POROFESOR_DATOS"):
    DATOS = Path(os.environ["POROFESOR_DATOS"])
elif CONGELADA:
    DATOS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Porofesor"
else:
    DATOS = RAIZ
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
