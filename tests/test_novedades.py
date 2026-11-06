"""Mapa del jungla rival, tu pool en la selección, LP de la partida, mapa de muertes y recortes."""

import unittest
from pathlib import Path

from deepprep import analisis as an
from deepprep import clips
from deepprep import revision as rv
from tests.test_analisis import jug, partida


class MapaJungla(unittest.TestCase):
    def test_se_lleva_al_lado_de_hoy(self):
        linea = {"pos": {"1": [[0, 0]] * 3 + [[3000, 7000]] * 4}}
        j = jug("j", 100, "JUNGLE", 64, True, pid=1)
        # Hoy juega en el equipo rojo: lo de aquella partida (azul) se refleja.
        mapa = an.mapa_posiciones([(None, j, linea)], 200)
        self.assertEqual(set(mapa), {"3", "4", "5", "6"})  # el minuto 2 está vacío y no cuenta
        self.assertEqual(mapa["3"], [[an.SUMA_X - 3000, an.SUMA_Y - 7000]])
        self.assertEqual(an.mapa_posiciones([(None, j, linea)], 100)["3"], [[3000, 7000]])

    def test_espejo_de_ida_y_vuelta(self):
        self.assertEqual(an.espejo(*an.espejo(1234, 5678)), (1234, 5678))


class PoolContra(unittest.TestCase):
    def test_opciones_con_datos_primero(self):
        pool = [(1, "JUNGLE"), (2, "JUNGLE"), (3, "MIDDLE"), (4, "JUNGLE")]
        registros = {1: [{"g": 1}] * 6 + [{"g": 0}] * 4, 2: [{"g": 1}] * 7 + [{"g": 0}] * 3, 4: [{"g": 1}] * 2}
        mias = {"yo"}
        partidas = [
            partida("a", [jug("yo", 100, "JUNGLE", 4, True, pid=2), jug("r", 200, "JUNGLE", 99, False, pid=7)]),
            partida("b", [jug("yo", 100, "JUNGLE", 4, False, pid=2), jug("r", 200, "JUNGLE", 50, True, pid=7)]),
        ]
        filas = an.pool_contra(pool, "JUNGLE", 99, registros, partidas, mias, minimo=8)
        self.assertEqual([f["campeon"] for f in filas], [2, 1, 4])  # el de mid no sale
        self.assertEqual((filas[0]["wr"], filas[1]["wr"], filas[2]["wr"]), (70, 60, None))
        self.assertEqual((filas[2]["yo_n"], filas[2]["yo_v"], filas[2]["vs_n"], filas[2]["vs_v"]), (2, 1, 1, 1))


class Liga(unittest.TestCase):
    def test_valor_con_cambio_de_division(self):
        antes = an.valor_liga("emerald", "I", 90)
        self.assertEqual(an.valor_liga("DIAMOND", "IV", 8) - antes, 18)
        self.assertEqual(an.valor_liga("MASTER", "I", 0) - an.valor_liga("DIAMOND", "I", 100), 0)
        self.assertIsNone(an.valor_liga("", "", 0))


class MapaMuertes(unittest.TestCase):
    def test_todo_desde_la_base_azul(self):
        revs = [
            {
                "id": "a",
                "equipo": 100,
                "campeon": "Diana",
                "gana": True,
                "muertes": [{"x": 100, "y": 200, "ms": 1, "t": "0:01", "asesino": "Yi"}],
            },
            {
                "id": "b",
                "equipo": 200,
                "campeon": "Diana",
                "gana": False,
                "muertes": [{"x": 100, "y": 200, "ms": 2, "t": "0:02", "asesino": "Yi"}],
            },
            {
                "id": "c",
                "campeon": "Diana",
                "gana": False,
                "muertes": [{"t": "0:03", "ms": 3}],
            },  # revisión antigua sin posiciones
            None,
        ]
        out = rv.mapa_muertes(revs)
        self.assertEqual([(m["id"], m["x"], m["y"]) for m in out], [("a", 100, 200), ("b", an.SUMA_X - 100, an.SUMA_Y - 200)])


class Recortes(unittest.TestCase):
    def test_tramo_dentro_de_un_trozo(self):
        archivos, desde, dur = clips.tramo(100_000, 10)  # muerte en el segundo 110 de la grabación
        self.assertEqual((archivos, desde, dur), (["r01_seg_000.mkv"], 90.0, clips.ANTES_S + clips.DESPUES_S))

    def test_tramo_entre_dos_trozos(self):
        archivos, desde, _ = clips.tramo(305_000, 5)  # segundo 310: empieza en el 290 del primer trozo
        self.assertEqual(archivos, ["r01_seg_000.mkv", "r01_seg_001.mkv"])
        self.assertEqual(desde, 290.0)

    def test_al_principio_no_empieza_antes_de_cero(self):
        archivos, desde, dur = clips.tramo(5_000, 2)
        self.assertEqual((archivos, desde), (["r01_seg_000.mkv"], 0.0))
        self.assertEqual(dur, 7 + clips.DESPUES_S)

    def test_orden_con_dos_trozos_usa_concat(self):
        orden = clips.orden_ffmpeg("ffmpeg", [Path("a.mkv"), Path("b.mkv")], 290.0, 24, Path("x.mp4"), Path("x.txt"))
        self.assertIn("concat", orden)
        self.assertEqual(orden[-1], "x.mp4")

    def test_sin_grabacion_no_hay_recorte(self):
        self.assertIsNone(clips.recortar("ffmpeg", Path("no-existe"), 0, {"ms": 60_000, "t": "1:00"}, 10))


if __name__ == "__main__":
    unittest.main()
