"""Captura del panel con Chrome sin ventana, para revisar el diseño.

Uso: py herramientas/captura.py URL salida.png [ancho alto]
Ejemplo: py herramientas/captura.py "http://127.0.0.1:5252/?vista=overlay" overlay.png 1180 620
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = [
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
]


def main():
    url, salida = sys.argv[1], Path(sys.argv[2]).resolve()
    ancho, alto = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1500, 950)
    exe = next(p for p in CHROME if p.is_file())
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [str(exe), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={perfil}",
             f"--window-size={ancho},{alto}", "--virtual-time-budget=5000", f"--screenshot={salida}", url],
            check=True, capture_output=True, timeout=60)
    print(salida)


if __name__ == "__main__":
    main()
