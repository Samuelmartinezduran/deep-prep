"""Pruebas. La carpeta del programa y los accesos directos del escritorio y de Inicio van a una carpeta
temporal antes de importar la app: ninguna prueba puede tocar los de verdad aunque se olvide de cambiarlos."""
import atexit
import os
import shutil
import tempfile

_PRUEBAS = tempfile.mkdtemp(prefix="deepprep-pruebas-")
atexit.register(shutil.rmtree, _PRUEBAS, True)
for _variable, _ruta in (("DEEPPREP_PROGRAMA", "Programs/DeepPrep"), ("DEEPPREP_ESCRITORIO", "Desktop/Deep Prep.lnk"),
                         ("DEEPPREP_INICIO", "Startup/Deep Prep.lnk")):
    os.environ[_variable] = os.path.join(_PRUEBAS, _ruta)
