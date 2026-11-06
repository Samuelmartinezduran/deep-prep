"""Pruebas del actualizador (sin red: GitHub de mentira)."""
import hashlib
import json
import io
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from deepprep import actualizador as act


def zip_con_exe():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("DeepPrep/DeepPrep.exe", b"exe")
        z.writestr("DeepPrep/_internal/algo.dll", b"dll")
    return b.getvalue()


class AppFalsa:
    fase, modo, grabador, revisando, al_salir = None, "previa", None, 0, None


class Actualizador(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parche = mock.patch.object(act, "CARPETA_DESCARGA", Path(self.tmp.name))
        self.parche.start()
        # Las notas de la versión descargada tampoco van a la carpeta de datos de verdad.
        self.parche_notas = mock.patch.object(act, "NOVEDADES", Path(self.tmp.name) / "novedades.json")
        self.parche_notas.start()
        self.parche_vista = mock.patch.object(act, "VISTA", Path(self.tmp.name) / "version_vista.txt")
        self.parche_vista.start()

    def tearDown(self):
        self.parche_vista.stop()
        self.parche_notas.stop()
        self.parche.stop()
        self.tmp.cleanup()

    def github(self, tag, datos, huella=None):
        huella = huella or hashlib.sha256(datos).hexdigest()
        rel = {"tag_name": tag, "assets": [{"name": "DeepPrep-9.9.9.zip", "browser_download_url": "zip"},
                                            {"name": "DeepPrep-9.9.9.zip.sha256", "browser_download_url": "sha"}]}
        respuestas = {"zip": datos, "sha": f"{huella}  DeepPrep-9.9.9.zip\n".encode()}
        return lambda url, binario=False: respuestas[url] if binario else rel

    def test_versiones(self):
        self.assertGreater(act.version("v1.0.10"), act.version("1.0.9"))
        self.assertEqual(act.version("raro"), (0,))

    def test_descarga_y_deja_lista_la_nueva(self):
        a = act.Actualizador(AppFalsa())
        with mock.patch.object(act, "_get", self.github("v9.9.9", zip_con_exe())):
            self.assertTrue(a.comprobar())
        self.assertEqual((a.estado["nueva"], a.estado["lista"]), ("9.9.9", True))
        self.assertTrue((a._carpeta_nueva / "DeepPrep.exe").is_file())

    def test_no_instala_si_la_huella_no_cuadra(self):
        a = act.Actualizador(AppFalsa())
        with mock.patch.object(act, "_get", self.github("v9.9.9", zip_con_exe(), huella="0" * 64)):
            with self.assertRaises(RuntimeError):
                a.comprobar()
        self.assertFalse(a.estado["lista"])

    def test_misma_version_no_hace_nada(self):
        a = act.Actualizador(AppFalsa())
        with mock.patch.object(act, "_get", self.github(f"v{act.__version__}", b"")):
            self.assertFalse(a.comprobar())

    def test_solo_se_instala_cuando_no_estorba(self):
        app = AppFalsa()
        a = act.Actualizador(app)
        self.assertTrue(a.puede_instalar())
        for cambio in ({"fase": "ChampSelect"}, {"fase": "InProgress", "modo": "juego"}, {"revisando": 1}):
            otra = AppFalsa()
            otra.__dict__.update(cambio)
            self.assertFalse(act.Actualizador(otra).puede_instalar(), cambio)

    def test_no_se_instala_con_la_ventana_a_la_vista(self):
        app = AppFalsa()
        app.ventana_visible = lambda: True
        self.assertFalse(act.Actualizador(app).puede_instalar())
        app.ventana_visible = lambda: False
        self.assertTrue(act.Actualizador(app).puede_instalar())
        # Sin ventana propia (panel en el navegador) cuenta si se ha mirado hace poco.
        sin_ventana = AppFalsa()
        sin_ventana.ultima_consulta = time.time()
        self.assertFalse(act.Actualizador(sin_ventana).puede_instalar())

    def test_sabe_cuanto_lleva_encendido_el_pc(self):
        self.assertGreater(act._segundos_encendido(), 0)

    def test_desde_el_codigo_no_se_instala(self):
        self.assertFalse(act.instalar_si_hace_falta())


if __name__ == "__main__":
    unittest.main()


class Novedades(unittest.TestCase):
    def test_solo_las_de_esta_version_y_una_vez(self):
        import tempfile
        from deepprep import __version__
        from deepprep import actualizador as act

        with tempfile.TemporaryDirectory() as d:
            original, vista = act.NOVEDADES, act.VISTA
            act.NOVEDADES, act.VISTA = Path(d) / "novedades.json", Path(d) / "version_vista.txt"
            try:
                a = act.Actualizador(app=None)
                self.assertIsNone(a.novedades())
                act.NOVEDADES.write_text(json.dumps({"version": "0.0.1", "notas": "vieja"}), encoding="utf-8")
                self.assertIsNone(a.novedades())  # de otra versión: no se enseña
                act.NOVEDADES.write_text(json.dumps({"version": __version__, "notas": "- algo"}), encoding="utf-8")
                self.assertEqual(a.novedades()["notas"], "- algo")
                self.assertFalse(a._faltan_novedades())  # ya están: no se vuelven a pedir
                a.novedades_vistas()
                self.assertIsNone(a.novedades())
                self.assertFalse(a._faltan_novedades())
                act.VISTA.write_text("1.0.0", encoding="utf-8")
                self.assertEqual(a._faltan_novedades(), __version__ != "1.0.0")
            finally:
                act.NOVEDADES, act.VISTA = original, vista
