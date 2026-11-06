"""herramientas/publicar.py sin empaquetar ni subir nada: qué comprueba antes, sus argumentos y dónde deja los zips.

PyInstaller, las comprobaciones y GitHub van de mentira: ninguna prueba construye la app ni sale a la red.
"""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_mudanza import RAIZ, cargar_publicar


def sin_salida():
    """Calla lo que imprime publicar.py (los «== paso»)."""
    return contextlib.redirect_stdout(io.StringIO())


class Comprobaciones(unittest.TestCase):
    def setUp(self):
        self.publicar = cargar_publicar()

    def test_pasa_lo_mismo_que_la_ci(self):
        ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        ordenes = [" ".join(orden) for _, orden in self.publicar.comprobaciones("python")]
        for paso_de_la_ci in (
            "ruff format --check",
            "ruff check",
            "mypy",
            "coverage run -m unittest discover -s tests -t .",
            "coverage report",
            "node --test",
        ):
            with self.subTest(paso_de_la_ci):
                self.assertIn(paso_de_la_ci, ci)
                self.assertTrue(any(paso_de_la_ci in o for o in ordenes), ordenes)

    def test_las_herramientas_con_el_python_que_se_le_da(self):
        for _, orden in self.publicar.comprobaciones("C:/entorno/python.exe"):
            self.assertIn(orden[0], ("C:/entorno/python.exe", "node"))

    def test_el_python_del_entorno_de_desarrollo_si_lo_hay(self):
        with tempfile.TemporaryDirectory() as d:
            nada, entorno = Path(d) / "no-existe", Path(d) / "venv"
            self.assertEqual(self.publicar.python_de_herramientas((nada,)), self.publicar.sys.executable)
            (entorno / "Scripts").mkdir(parents=True)
            (entorno / "Scripts" / "python.exe").write_bytes(b"")
            self.assertEqual(self.publicar.python_de_herramientas((nada, entorno)), str(entorno / "Scripts" / "python.exe"))

    def test_las_pasa_todas_aunque_falle_alguna(self):
        hechas = []

        def ejecutar(orden, cwd):
            hechas.append(orden[0])
            if orden[0] == "no-esta":
                raise FileNotFoundError(orden[0])
            return subprocess.CompletedProcess(orden, 1 if orden[0] == "falla" else 0)

        lista = [("A", ["bien"]), ("B", ["falla"]), ("C", ["no-esta"]), ("D", ["bien"])]
        with sin_salida():
            fallan = self.publicar.pasar_comprobaciones(lista, ejecutar=ejecutar)
        self.assertEqual(fallan, ["B", "C"])
        self.assertEqual(hechas, ["bien", "falla", "no-esta", "bien"])


class Argumentos(unittest.TestCase):
    def setUp(self):
        self.publicar = cargar_publicar()

    def test_publicar_como_siempre(self):
        leer = self.publicar.leer_argumentos
        self.assertEqual(leer([]), (None, None, False, None))
        self.assertEqual(leer(["2.0.1", "- Qué cambia", "--puente"]), ("2.0.1", "- Qué cambia", True, None))
        self.assertEqual(leer(["--puente", "2.0.1"]), ("2.0.1", None, True, None))

    def test_solo_construir(self):
        with tempfile.TemporaryDirectory() as d:
            v, notas, puente, solo = self.publicar.leer_argumentos(["2.0.0", "--solo-construir", d, "--puente"])
            self.assertEqual((v, notas, puente, solo), ("2.0.0", None, True, Path(d).resolve()))
            for sin_carpeta in (["--solo-construir"], ["--solo-construir", "--puente"]):
                with self.subTest(sin_carpeta), self.assertRaises(SystemExit):
                    self.publicar.leer_argumentos(sin_carpeta)

    def test_carpetas(self):
        emp = self.publicar.EMP
        self.assertEqual(self.publicar.carpetas(None), (emp, emp, emp / "puente"))
        otra = Path("C:/construir")
        self.assertEqual(self.publicar.carpetas(otra), (otra, otra, otra / "puente"))


class Main(unittest.TestCase):
    """main() con todo lo que tarda o sale fuera de mentira: qué se llama y con qué carpetas."""

    def setUp(self):
        self.publicar = cargar_publicar()
        self.llamadas = mock.Mock()
        self.llamadas.pasar_comprobaciones.return_value = []
        self.llamadas.empaquetar.side_effect = lambda salida: salida / "dist" / "DeepPrep"
        self.llamadas.comprimir.side_effect = lambda v, puente=False, dist=None, carpeta=None: carpeta / f"DeepPrep-{v}.zip"
        for nombre in ("pasar_comprobaciones", "poner_version", "empaquetar", "comprimir", "publicar", "token"):
            parche = mock.patch.object(self.publicar, nombre, getattr(self.llamadas, nombre))
            parche.start()
            self.addCleanup(parche.stop)

    def main(self, *argv):
        with sin_salida():
            self.publicar.main(list(argv))

    def test_solo_construir_no_sube_nada_ni_cambia_la_version(self):
        with tempfile.TemporaryDirectory() as d:
            solo = Path(d).resolve()
            self.main(self.publicar.leer_version(), "--puente", "--solo-construir", d)
            self.llamadas.empaquetar.assert_called_once_with(solo)
            self.assertEqual([c.kwargs["carpeta"] for c in self.llamadas.comprimir.call_args_list], [solo, solo / "puente"])
            self.assertEqual([c.kwargs.get("puente", False) for c in self.llamadas.comprimir.call_args_list], [False, True])
        self.llamadas.poner_version.assert_not_called()
        self.llamadas.publicar.assert_not_called()
        self.llamadas.token.assert_not_called()

    def test_solo_construir_con_otra_version_no_hace_nada(self):
        with self.assertRaises(SystemExit):
            self.main("9.9.9", "--solo-construir", "C:/construir")
        self.llamadas.pasar_comprobaciones.assert_not_called()
        self.llamadas.empaquetar.assert_not_called()
        self.llamadas.poner_version.assert_not_called()

    def test_si_falla_una_comprobacion_no_se_publica(self):
        self.llamadas.pasar_comprobaciones.return_value = ["Tipos (mypy)"]
        with self.assertRaisesRegex(SystemExit, "mypy"):
            self.main("2.0.1", "Notas", "--puente")
        self.llamadas.poner_version.assert_not_called()
        self.llamadas.empaquetar.assert_not_called()
        self.llamadas.publicar.assert_not_called()

    def test_publicar_sigue_igual(self):
        emp = self.publicar.EMP
        self.main("2.0.1", "Notas", "--puente")
        self.llamadas.poner_version.assert_called_once_with("2.0.1")
        self.llamadas.empaquetar.assert_called_once_with(emp)
        zip_ruta, zip_puente = emp / "DeepPrep-2.0.1.zip", emp / "puente" / "DeepPrep-2.0.1.zip"
        self.assertEqual(
            self.llamadas.publicar.call_args_list,
            [mock.call("2.0.1", "Notas", zip_ruta), mock.call("2.0.1", "Notas", zip_puente, self.publicar.REPO_PUENTE)],
        )

    def test_sin_version_solo_empaqueta(self):
        self.main()
        self.llamadas.poner_version.assert_not_called()
        self.llamadas.empaquetar.assert_called_once_with(self.publicar.EMP)
        self.llamadas.publicar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
