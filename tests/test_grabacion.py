"""Pruebas del grabador integrado (lo que no necesita juego ni pantalla)."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from deepprep import grabacion as g


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


if __name__ == "__main__":
    unittest.main()
