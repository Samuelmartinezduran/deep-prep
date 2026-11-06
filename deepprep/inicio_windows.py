"""Arranque con Windows: un acceso directo en la carpeta Inicio que abre la app con la ventana escondida.

Así el recolector de duelos sigue trabajando con el LoL cerrado y el overlay está listo al jugar.
"""

import os
import shutil
import sys
from pathlib import Path

from . import config
from .sistema import crear_acceso_directo

# DEEPPREP_INICIO lo manda a otro sitio (para probar sin tocar la carpeta Inicio de verdad).
ACCESO = Path(
    os.environ.get("DEEPPREP_INICIO")
    or Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/Deep Prep.lnk"
)
# El de Porofesor (hasta la 1.0.2): lo quita actualizador.quitar_restos_de_porofesor si era el de la app instalada.
ACCESO_VIEJO = ACCESO.with_name("Porofesor.lnk")


def activo() -> bool:
    return ACCESO.exists()


def poner(encendido: bool) -> str:
    """Crea o quita el acceso directo. Devuelve un texto de error o ''."""
    if not encendido:
        try:
            ACCESO.unlink(missing_ok=True)
        except OSError as e:
            return f"No se pudo quitar el arranque con Windows: {e}"
        return ""
    pyw: str | None
    if config.CONGELADA:
        pyw, argumentos = sys.executable, "--oculta"
    else:
        pyw, argumentos = shutil.which("pyw"), "-X utf8 -m deepprep --oculta"
    if not pyw:
        return "No encuentro pyw para arrancar con Windows."
    # Arranca en la RAIZ: desde el código, en la carpeta de pyw no se encontraría el paquete para "-m deepprep".
    r = crear_acceso_directo(
        ACCESO,
        pyw,
        argumentos,
        "Deep Prep (en segundo plano)",
        carpeta=config.RAIZ,
        icono=config.RUTA_WEB / "icono.ico",
        texto=True,
    )
    return "" if r.returncode == 0 and ACCESO.exists() else f"No se pudo crear el arranque con Windows: {r.stderr.strip()[:200]}"
