"""config.json y clave.txt: se escriben de golpe (nunca a medias) y un config.json roto no se lleva tus datos."""

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from deepprep import config


class Configuracion(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.carpeta = Path(d.name)
        self.ruta = self.carpeta / "config.json"
        self.copia = self.carpeta / "config.json.copia"
        self.rota = self.carpeta / "config.json.roto"
        for p in (
            mock.patch.object(config, "RUTA_CONFIG", self.ruta),
            mock.patch.object(config, "RUTA_CLAVE", self.carpeta / "clave.txt"),
            mock.patch.object(config, "_no_pisar", ""),
        ):
            self.enterContext(p)
        self.salida = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def sobrantes(self):
        """Temporales que hayan quedado en la carpeta."""
        return [p.name for p in self.carpeta.iterdir() if p.suffix == ".tmp"]

    def test_guardar_deja_el_archivo_y_su_copia(self):
        config.guardar(dict(config.POR_DEFECTO, cuentas=["Yo#EUW"]))
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8"))["cuentas"], ["Yo#EUW"])
        self.assertEqual(self.copia.read_text(encoding="utf-8"), self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(self.sobrantes(), [])

    def test_si_falla_a_medias_queda_el_de_antes(self):
        config.guardar({"cuentas": ["Yo#EUW"]})
        antes = self.ruta.read_text(encoding="utf-8")
        with mock.patch.object(config.os, "replace", side_effect=OSError("disco lleno")), self.assertRaises(OSError):
            config.guardar({"cuentas": []})
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)
        self.assertEqual(self.sobrantes(), [])  # ni el temporal a medias

    def test_reintenta_si_windows_no_deja_cambiarlo(self):
        reemplazar, veces = config.os.replace, []

        def ocupado_la_primera_vez(origen, destino):
            veces.append(destino)
            if len(veces) == 1:
                raise PermissionError("lo tiene abierto el antivirus")
            reemplazar(origen, destino)

        with mock.patch.object(config.os, "replace", ocupado_la_primera_vez), mock.patch.object(config.time, "sleep"):
            config.guardar_clave("  RGAPI-nueva  ")
        self.assertEqual(config.leer_clave(), "RGAPI-nueva")
        self.assertEqual(len(veces), 2)
        self.assertEqual(self.sobrantes(), [])

    def test_hilos_a_la_vez_nunca_lo_dejan_roto(self):
        def escribir(n):
            for i in range(20):
                config.guardar({"cuentas": [f"Hilo{n}#{i}"] * 50})

        hilos = [threading.Thread(target=escribir, args=(n,)) for n in range(4)]
        for h in hilos:
            h.start()
        for _ in range(50):
            self.assertIn("cuentas", config.cargar())  # se lee entero en cualquier momento
        for h in hilos:
            h.join()
        self.assertEqual(len(json.loads(self.ruta.read_text(encoding="utf-8"))["cuentas"]), 50)
        self.assertFalse(self.rota.exists())
        self.assertEqual(self.sobrantes(), [])

    def test_roto_tira_de_la_copia_y_aparta_el_roto(self):
        config.guardar(dict(config.POR_DEFECTO, cuentas=["Yo#EUW"]))
        self.ruta.write_text('{"cuentas": ["Yo#EU', encoding="utf-8")  # cortado a medias
        cfg = config.cargar()
        self.assertEqual(cfg["cuentas"], ["Yo#EUW"])
        self.assertEqual(self.rota.read_text(encoding="utf-8"), '{"cuentas": ["Yo#EU')  # el roto no se pierde
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8"))["cuentas"], ["Yo#EUW"])  # rehecho
        self.assertIn("config.json.roto", self.salida.getvalue())
        config.guardar(dict(cfg, plataforma="na1"))  # y se sigue guardando con normalidad
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8"))["cuentas"], ["Yo#EUW"])

    def test_roto_sin_copia_lo_guarda_aparte(self):
        self.ruta.write_text("[1, 2", encoding="utf-8")
        cfg = config.cargar()
        self.assertEqual(cfg, config.POR_DEFECTO)
        self.assertEqual(self.rota.read_text(encoding="utf-8"), "[1, 2")
        self.assertIn("valores por defecto", self.salida.getvalue())

    def test_si_no_se_puede_apartar_no_se_escribe_encima(self):
        config.guardar(dict(config.POR_DEFECTO, cuentas=["Copia#EUW"]))
        self.ruta.write_text("no es json", encoding="utf-8")
        with mock.patch.object(config.os, "replace", side_effect=PermissionError("bloqueado")):
            cfg = config.cargar()
        self.assertEqual(cfg["cuentas"], ["Copia#EUW"])  # lo de la copia, en memoria
        config.guardar(dict(cfg, cuentas=[]))
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), "no es json")  # tus datos, intactos
        self.assertIn("No guardo config.json", self.salida.getvalue())

    def test_un_momento_ocupado_no_cuenta_como_roto(self):
        config.guardar({"cuentas": ["Yo#EUW"]})
        leer = Path.read_text
        veces: list[Path] = []

        def ocupado_la_primera_vez(ruta, *a, **k):
            if ruta == self.ruta and not veces:
                veces.append(ruta)
                raise PermissionError("lo tiene abierto el antivirus")
            return leer(ruta, *a, **k)

        with mock.patch.object(Path, "read_text", ocupado_la_primera_vez), mock.patch.object(config.time, "sleep"):
            self.assertEqual(config.cargar()["cuentas"], ["Yo#EUW"])
        self.assertEqual(veces, [self.ruta])
        self.assertFalse(self.rota.exists())  # no se ha apartado nada
        self.assertNotIn("AVISO", self.salida.getvalue())

    def test_un_json_que_no_es_un_objeto_cuenta_como_roto(self):
        self.ruta.write_text("null", encoding="utf-8")
        self.assertEqual(config.cargar(), config.POR_DEFECTO)
        self.assertTrue(self.rota.is_file())

    def test_sin_config_se_crea(self):
        self.assertEqual(config.cargar(), config.POR_DEFECTO)
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8")), config.POR_DEFECTO)

    def test_cargar_uno_bueno_renueva_la_copia(self):
        self.ruta.write_text(json.dumps({"cuentas": ["A mano#EUW"]}), encoding="utf-8")
        self.assertEqual(config.cargar()["cuentas"], ["A mano#EUW"])
        self.assertEqual(json.loads(self.copia.read_text(encoding="utf-8")), {"cuentas": ["A mano#EUW"]})


if __name__ == "__main__":
    unittest.main()
