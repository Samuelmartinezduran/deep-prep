"""Pruebas. La carpeta del programa y los accesos directos del escritorio y de Inicio van a una carpeta
temporal antes de importar la app: ninguna prueba puede tocar los de verdad aunque se olvide de cambiarlos."""

import atexit
import contextlib
import io
import logging
import os
import shutil
import tempfile

_PRUEBAS = tempfile.mkdtemp(prefix="deepprep-pruebas-")
atexit.register(shutil.rmtree, _PRUEBAS, True)
for _variable, _ruta in (
    ("DEEPPREP_PROGRAMA", "Programs/DeepPrep"),
    ("DEEPPREP_ESCRITORIO", "Desktop/Deep Prep.lnk"),
    ("DEEPPREP_INICIO", "Startup/Deep Prep.lnk"),
):
    os.environ[_variable] = os.path.join(_PRUEBAS, _ruta)


@contextlib.contextmanager
def registro_de(nombre="deepprep"):
    """Lo que apunta en el registro ese módulo (y los de debajo) mientras dura el with, sin que salga por la consola.

    Devuelve el StringIO donde va quedando, con todos los niveles.
    """
    salida = io.StringIO()
    manejador = logging.StreamHandler(salida)
    registro = logging.getLogger(nombre)
    nivel = registro.level
    registro.addHandler(manejador)
    registro.setLevel(logging.DEBUG)
    try:
        yield salida
    finally:
        registro.setLevel(nivel)
        registro.removeHandler(manejador)
