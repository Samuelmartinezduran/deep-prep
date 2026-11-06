"""Sirve el panel de la demo (deepprep/demo) en un puerto fijo, sin ventanas, para diseñarlo y revisarlo sin partida.

Uso: py herramientas/maqueta.py [estado.json] [--escena seleccion|carga|juego] [--puerto 5252] [--novedades]

Es la demo (py -m deepprep --demo --sin-ventana) con lo que viene bien al diseñar:
- estado.json: el panel de ese estado en vez del de la demo, p. ej. el que guarda herramientas/simular_propia.py en
  herramientas/maquetas/partida.json (un nombre suelto se busca también en herramientas/).
- --novedades: el aviso de una versión nueva ya descargada y las novedades de la recién instalada, como los ven los
  amigos al actualizarse.
Nada va a tus datos ni a la carpeta del proyecto: todo va a una carpeta temporal que se borra al cerrar (Ctrl+C).
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

NOTAS = (
    "Interfaz nueva y más datos para jugar mejor.\n"
    "- Tu pool contra el rival en la selección de campeón\n"
    "- Mapa de dónde está el jungla rival en sus primeros minutos\n"
    "- Clips de cada muerte en la revisión"
)


def opcion(nombre, defecto=None):
    return sys.argv[sys.argv.index(nombre) + 1] if nombre in sys.argv[:-1] else defecto


def archivo_de_estado():
    valores = {opcion("--escena"), opcion("--modo"), opcion("--puerto")}
    libres = [a for a in sys.argv[1:] if not a.startswith("--") and a not in valores]
    if not libres:
        return None
    archivo = Path(libres[0])
    if not archivo.is_absolute() and not archivo.exists():
        archivo = AQUI / archivo
    return archivo


def main():
    carpeta = Path(tempfile.mkdtemp(prefix="deepprep-maqueta-"))
    # Antes de importar deepprep: así sus datos (las imágenes de Data Dragon) también van a la carpeta temporal.
    os.environ["DEEPPREP_DATOS"] = str(carpeta)
    from deepprep import __version__, servidor
    from deepprep.demo import ESCENA_INICIAL, AppDemo

    archivo = archivo_de_estado()
    panel = json.loads(archivo.read_text(encoding="utf-8"))["panel"] if archivo else None
    novedades = version = None
    if "--novedades" in sys.argv:
        novedades = {"version": __version__, "notas": NOTAS}
        *resto, ultimo = __version__.split(".")
        nueva = ".".join([*resto, str(int(ultimo) + 1)])
        version = {"version": __version__, "nueva": nueva, "lista": True, "error": ""}
    escena = opcion("--escena") or opcion("--modo") or ESCENA_INICIAL  # --modo: el nombre de antes
    app = AppDemo(carpeta, escena=escena, panel=panel, novedades=novedades, version=version)
    puerto = int(opcion("--puerto", "5252"))
    srv = servidor.crear(app, puerto, post=app.rutas())
    print(f"Maqueta en http://127.0.0.1:{puerto}/ (escena {app.escena}); Ctrl+C para cerrarla", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == "__main__":
    main()
