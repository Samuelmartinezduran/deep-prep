"""Pruebas del grabador integrado (lo que no necesita juego ni pantalla)."""

import contextlib
import gc
import io
import json
import msvcrt
import os
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from deepprep import app
from deepprep import grabacion as g
from deepprep import recolector as rec


class Limpieza(unittest.TestCase):
    def test_borra_las_mas_viejas_hasta_caber(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for i, nombre in enumerate(["2026-10-01_partida1", "2026-10-02_partida1", "2026-10-03_partida1"]):
                c = base / nombre
                c.mkdir()
                (c / "r01_seg_000.mkv").write_bytes(b"x" * 1024)
                os.utime(c, (time.time() - 1000 + i, time.time() - 1000 + i))
            otra = base / "mis cosas"
            otra.mkdir()  # lo que no es una partida grabada no se toca
            actual = base / "2026-10-03_partida1"
            borradas = g.limpiar(base, 2048 / 1024**3, actual=actual)
            self.assertEqual(borradas, ["2026-10-01_partida1"])
            self.assertTrue(actual.is_dir() and otra.is_dir())
            self.assertEqual(g.limpiar(base, 0), [])  # 0 = no borrar nunca

    def test_cpu_sin_probar_la_grafica(self):
        self.assertEqual(g.elegir_codificador("ffmpeg-que-no-existe", "cpu"), ("procesador", g.CPU))
        self.assertEqual(g.elegir_codificador("ffmpeg-que-no-existe", "auto"), ("procesador", g.CPU))


class Registro(unittest.TestCase):
    def test_carpeta_del_registro(self):
        with tempfile.TemporaryDirectory() as d:
            original = g.RUTA_LOG
            g.RUTA_LOG = Path(d) / "grabacion.log"
            try:
                g.RUTA_LOG.write_text("GRABANDO en C:\\Videos\\LoL-coach\\2026-10-14_partida2\nPantalla 0\n", encoding="utf-8")
                self.assertEqual(g._carpeta_del_registro(solo_en_curso=True).name, "2026-10-14_partida2")
                g.RUTA_LOG.write_text(g.RUTA_LOG.read_text(encoding="utf-8") + "TERMINADO: 30 min\n", encoding="utf-8")
                self.assertIsNone(g._carpeta_del_registro(solo_en_curso=True))
                self.assertEqual(g._carpeta_del_registro().name, "2026-10-14_partida2")
            finally:
                g.RUTA_LOG = original


class Cerrojo(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.ruta = Path(d.name) / "grabacion.lock"
        self.enterContext(mock.patch.object(g, "RUTA_CERROJO", self.ruta))
        self.grabar = self.enterContext(mock.patch.object(g, "_grabar"))

    def test_si_ya_hay_otro_grabando_no_deja_el_cerrojo_abierto(self):
        with open(self.ruta, "a") as otro:  # el otro proceso de grabación
            msvcrt.locking(otro.fileno(), msvcrt.LK_NBLCK, 1)
            gc.collect()  # lo que hayan dejado otras pruebas no cuenta
            with warnings.catch_warnings(record=True) as avisos:
                warnings.simplefilter("always", ResourceWarning)
                g.grabar({})
                gc.collect()
            msvcrt.locking(otro.fileno(), msvcrt.LK_UNLCK, 1)
        self.grabar.assert_not_called()
        # Sin cerrarlo, Python lo cierra al soltarlo y avisa: «unclosed file <... name='...grabacion.lock'>».
        self.assertEqual([str(a.message) for a in avisos if "grabacion.lock" in str(a.message)], [])
        self.ruta.unlink()  # en Windows no se podría con el archivo aún abierto

    def test_mientras_graba_lo_tiene_cogido_y_al_acabar_lo_suelta(self):
        ocupado = []
        self.grabar.side_effect = lambda *a: ocupado.append(g._cerrojo_ocupado())
        g.grabar({}, prueba_seg=10)
        self.grabar.assert_called_once_with({}, 5, 100, 10)
        self.assertEqual(ocupado, [True])
        self.assertFalse(g._cerrojo_ocupado())
        self.ruta.unlink()

    def test_el_recolector_tampoco_lo_deja_abierto(self):
        ruta = self.ruta.with_name("recolector.lock")
        with mock.patch.object(rec, "RUTA_CERROJO", ruta), mock.patch.object(rec.config, "cargar", dict):
            r = rec.Recolector(None, str, set(), list, regiones=())
            with open(ruta, "a") as otro, contextlib.redirect_stdout(io.StringIO()):
                msvcrt.locking(otro.fileno(), msvcrt.LK_NBLCK, 1)
                self.assertFalse(r.arrancar())
                msvcrt.locking(otro.fileno(), msvcrt.LK_UNLCK, 1)
        self.assertIsNone(r._cerrojo)
        ruta.unlink()  # sin un archivo abierto por medio


class Series(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.carpeta = Path(d.name)

    def trozos(self, *nombres):
        for nombre in nombres:
            (self.carpeta / nombre).write_bytes(b"x")

    def test_el_grabador_apunta_cuando_empieza_cada_serie(self):
        self.trozos("r01_seg_000.mkv", "r01_seg_001.mkv", "r02_seg_000.mkv")
        g.apuntar_serie(self.carpeta, 1, 1000.0)
        g.apuntar_serie(self.carpeta, 2, 1612.25)
        self.assertEqual(g.inicio_de_series(self.carpeta), {1: 1000.0, 2: 1612.25})
        self.assertEqual(json.loads((self.carpeta / g.SERIES).read_text(encoding="utf-8")), {"1": 1000.0, "2": 1612.25})

    def test_grabacion_de_antes_sin_series_json(self):
        # Sin series.json vale la fecha de creación del primer trozo de cada serie (lo que se usaba con la serie 1).
        self.trozos("r01_seg_000.mkv", "r01_seg_001.mkv", "r02_seg_000.mkv", "r02_seg_001.mkv", "notas.txt")
        creado = {n: (self.carpeta / f"r0{n}_seg_000.mkv").stat().st_birthtime for n in (1, 2)}
        self.assertEqual(g.inicio_de_series(self.carpeta), creado)

    def test_series_json_roto_o_a_medias(self):
        self.trozos("r01_seg_000.mkv", "r02_seg_000.mkv")
        creado = {n: (self.carpeta / f"r0{n}_seg_000.mkv").stat().st_birthtime for n in (1, 2)}
        series_json = self.carpeta / g.SERIES
        for roto in ('{"1": 1000.0, "2": ', "[]", '{"uno": "ayer"}'):
            series_json.write_text(roto, encoding="utf-8")
            self.assertEqual(g.inicio_de_series(self.carpeta), creado)  # con las fechas de los archivos
        series_json.write_text('{"1": 1000.0}', encoding="utf-8")  # la serie 2 sin apuntar
        self.assertEqual(g.inicio_de_series(self.carpeta), {1: 1000.0, 2: creado[2]})
        series_json.write_text("[]", encoding="utf-8")
        g.apuntar_serie(self.carpeta, 2, 1500.0)  # sobre uno roto se empieza de cero sin fallar
        self.assertEqual(g.inicio_de_series(self.carpeta), {1: creado[1], 2: 1500.0})

    def test_serie_sin_trozos_no_cuenta(self):
        self.trozos("r01_seg_000.mkv")
        g.apuntar_serie(self.carpeta, 1, 1000.0)
        g.apuntar_serie(self.carpeta, 2, 1300.0)  # ffmpeg no llegó a escribir nada
        self.assertEqual(g.inicio_de_series(self.carpeta), {1: 1000.0})
        self.assertEqual(g.inicio_de_series(self.carpeta / "no-existe"), {})

    def test_desfase_de_cada_serie_respecto_a_la_partida(self):
        self.trozos("r01_seg_000.mkv", "r02_seg_000.mkv")
        g.apuntar_serie(self.carpeta, 1, 1000.0)
        g.apuntar_serie(self.carpeta, 2, 1630.0)
        # La partida empezó (0:00) a los 30 s de grabar; la serie 2, a los 10:00 de partida.
        self.assertEqual(app._desfase(self.carpeta, 1_030_000), {1: 30, 2: -600})
        self.assertIsNone(app._desfase(self.carpeta / "no-existe", 1_030_000))
        self.assertIsNone(app._desfase(None, 1_030_000))


if __name__ == "__main__":
    unittest.main()
