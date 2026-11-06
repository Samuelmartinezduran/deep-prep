"""Piezas de Windows que usan varios módulos: procesos sin consola, accesos directos y hablar con la copia en marcha."""

import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

# Los procesos que lanza la app (ffmpeg, PowerShell...) no abren una ventana de consola.
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def crear_acceso_directo(
    destino: str | Path,
    objetivo: str | Path,
    argumentos: str = "",
    descripcion: str = "Deep Prep",
    carpeta: str | Path | None = None,
    icono: str | Path | None = None,
    texto: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Crea (o rehace) un acceso directo .lnk con PowerShell y devuelve lo que ha hecho PowerShell (subprocess.run).

    carpeta: dónde arranca (por defecto, la del objetivo). icono: su .ico (por defecto, el del objetivo).
    texto: la salida de PowerShell como texto (si no, en bytes).
    """
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:DESTINO); $s.TargetPath=$env:OBJETIVO;"
        "$s.Arguments=$env:ARGS; $s.WorkingDirectory=$env:CARPETA; $s.Description=$env:DESC;"
        + (" $s.IconLocation=$env:ICONO;" if icono else "")
        + " $s.Save()"
    )
    entorno = dict(
        os.environ,
        DESTINO=str(destino),
        OBJETIVO=str(objetivo),
        ARGS=argumentos,
        CARPETA=str(carpeta or Path(objetivo).parent),
        DESC=descripcion,
        ICONO=str(icono or ""),
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps], env=entorno, capture_output=True, text=texto, creationflags=SIN_VENTANA
    )


def pedir_a_la_copia_en_marcha(url: str, ruta: str, espera: float = 5) -> bytes:
    """POST vacío a la API de la copia de la app que ya está en marcha (en url); devuelve el cuerpo de la respuesta.

    Lleva el Origin de su propio panel: es lo único que acepta. Lanza OSError si no hay ninguna escuchando.
    """
    pet = urllib.request.Request(url + ruta, data=b"{}", headers={"Origin": url.rstrip("/"), "Content-Type": "application/json"})
    with urllib.request.urlopen(pet, timeout=espera) as r:
        cuerpo: bytes = r.read()
        return cuerpo
