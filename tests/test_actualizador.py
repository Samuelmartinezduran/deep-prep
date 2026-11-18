"""Pruebas del actualizador (sin red: GitHub de mentira)."""

import hashlib
import io
import json
import tempfile
import time
import unittest
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

from deepprep import actualizador as act


def zip_con_exe():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("DeepPrep/DeepPrep.exe", b"exe")
        z.writestr("DeepPrep/_internal/algo.dll", b"dll")
    return b.getvalue()


class AppFalsa:
    fase: str | None = None
    modo = "previa"
    grabador: Any = None
    revisando = 0
    al_salir: Any = None
    # Solo si la prueba los pone (el actualizador los mira con getattr).
    ventana_visible: Callable[[], bool]
    ultima_consulta: float


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
        rel = {
            "tag_name": tag,
            "assets": [
                {"name": "DeepPrep-9.9.9.zip", "browser_download_url": "zip"},
                {"name": "DeepPrep-9.9.9.zip.sha256", "browser_download_url": "sha"},
            ],
        }
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
        assert a._carpeta_nueva is not None
        self.assertTrue((a._carpeta_nueva / "DeepPrep.exe").is_file())

    def test_no_instala_si_la_huella_no_cuadra(self):
        a = act.Actualizador(AppFalsa())
        with (
            mock.patch.object(act, "_get", self.github("v9.9.9", zip_con_exe(), huella="0" * 64)),
            self.assertRaises(RuntimeError),
        ):
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

    def lista(self, app):
        """Un actualizador con la versión 9.9.9 ya descargada."""
        a = act.Actualizador(app)
        with mock.patch.object(act, "_get", self.github("v9.9.9", zip_con_exe())):
            a.comprobar()
        return a

    def test_por_que_no_se_puede_ahora(self):
        casos = {
            "Matchmaking": "en cola",
            "ReadyCheck": "en cola",
            "ChampSelect": "selección",
            "InProgress": "en partida",
            "WaitingForStats": "en partida",
        }
        for fase, texto in casos.items():
            app = AppFalsa()
            app.fase = fase
            self.assertIn(texto, act.Actualizador(app).que_estorba(), fase)
        app = AppFalsa()
        app.revisando = 1
        self.assertIn("revisión", act.Actualizador(app).que_estorba())
        app = AppFalsa()
        app.grabador = mock.Mock(activa=lambda: True)
        self.assertIn("grabación", act.Actualizador(app).que_estorba())
        for libre in (None, "Lobby", "EndOfGame"):
            app = AppFalsa()
            app.fase = libre
            self.assertEqual(act.Actualizador(app).que_estorba(), "", libre)

    def test_actualizar_ahora_sin_version_nueva(self):
        r = act.Actualizador(AppFalsa()).actualizar_ahora()
        self.assertFalse(r["ok"])
        self.assertIn("No hay", r["error"])

    def test_actualizar_ahora_en_partida_no_instala(self):
        app = AppFalsa()
        app.fase, app.modo = "InProgress", "juego"
        a = self.lista(app)
        with mock.patch.object(act.subprocess, "Popen") as popen:
            r = a.actualizar_ahora()
        self.assertEqual(r, {"ok": False, "error": "Ahora no: estás en partida." + act.OTRA_VEZ})
        popen.assert_not_called()

    def test_actualizar_ahora_con_la_ventana_a_la_vista(self):
        # Sola no se instala con la ventana a la vista; con el botón sí, y la nueva se abre a la vista.
        app = AppFalsa()
        app.ventana_visible = lambda: True
        app.al_salir = mock.Mock()
        a = self.lista(app)
        self.assertFalse(a.puede_instalar())
        with mock.patch.object(act.subprocess, "Popen") as popen, mock.patch.object(act.threading, "Timer") as timer:
            self.assertEqual(a.actualizar_ahora(), {"ok": True})
            # El cierre va con un poco de retraso (que la ventana diga «Instalando»): aquí se lanza a mano.
            (espera, funcion), extra = timer.call_args
            self.assertEqual(espera, 0.5)
            funcion(**extra["kwargs"])
        orden = popen.call_args.args[0]
        self.assertEqual(orden[1:3], ["--actualizar", str(act.os.getpid())])
        self.assertEqual(orden[-1], "--mostrar")
        app.al_salir.assert_called_once()

    def test_la_sola_se_abre_escondida(self):
        app = AppFalsa()
        app.al_salir = mock.Mock()
        a = self.lista(app)
        with mock.patch.object(act.subprocess, "Popen") as popen:
            a.aplicar()
        self.assertEqual(popen.call_args.args[0][-1], "--oculta")

    def test_el_boton_y_el_bucle_a_la_vez_instalan_una_vez(self):
        app = AppFalsa()
        app.al_salir = mock.Mock()
        a = self.lista(app)
        with mock.patch.object(act.subprocess, "Popen") as popen:
            a.aplicar(mostrar=True)
            a.aplicar()
        popen.assert_called_once()
        app.al_salir.assert_called_once()

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
                novedades = a.novedades()
                assert novedades is not None
                self.assertEqual(novedades["notas"], "- algo")
                self.assertFalse(a._faltan_novedades())  # ya están: no se vuelven a pedir
                a.novedades_vistas()
                self.assertIsNone(a.novedades())
                self.assertFalse(a._faltan_novedades())
                act.VISTA.write_text("1.0.0", encoding="utf-8")
                self.assertEqual(a._faltan_novedades(), __version__ != "1.0.0")
            finally:
                act.NOVEDADES, act.VISTA = original, vista
