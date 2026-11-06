"""Arranque con Windows: un acceso directo en la carpeta Inicio que abre la app con la ventana escondida.

Así el recolector de duelos sigue trabajando con el LoL cerrado y el overlay está listo al jugar.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

ACCESO = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/Porofesor.lnk"


def activo():
    return ACCESO.exists()


def poner(encendido):
    """Crea o quita el acceso directo. Devuelve un texto de error o ''."""
    if not encendido:
        try:
            ACCESO.unlink(missing_ok=True)
        except OSError as e:
            return f"No se pudo quitar el arranque con Windows: {e}"
        return ""
    if config.CONGELADA:
        pyw, argumentos = sys.executable, "--oculta"
    else:
        pyw, argumentos = shutil.which("pyw"), "-X utf8 -m porofesor --oculta"
    if not pyw:
        return "No encuentro pyw para arrancar con Windows."
    icono = config.RUTA_WEB / "icono.ico"
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ACCESO);"
        "$s.TargetPath=$env:PYW; $s.Arguments=$env:ARGS;"
        "$s.WorkingDirectory=$env:RAIZ; $s.IconLocation=$env:ICONO; $s.Description='Porofesor (en segundo plano)'; $s.Save()"
    )
    entorno = dict(os.environ, ACCESO=str(ACCESO), PYW=pyw, ARGS=argumentos, RAIZ=str(config.RAIZ), ICONO=str(icono))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=entorno, capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "" if r.returncode == 0 and ACCESO.exists() else f"No se pudo crear el arranque con Windows: {r.stderr.strip()[:200]}"
