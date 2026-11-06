"""Mapa del jungla rival, tu pool en la selección, LP de la partida, mapa de muertes y recortes."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        assert antes is not None
        self.assertEqual(an.valor_liga("DIAMOND", "IV", 8), antes + 18)
        self.assertEqual(an.valor_liga("MASTER", "I", 0), an.valor_liga("DIAMOND", "I", 100))
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


def tramo(ms, desfase_s):
    """clips.tramo, que en estas pruebas siempre da un recorte."""
    corte = clips.tramo(ms, desfase_s)
    assert corte is not None
    return corte


class Recortes(unittest.TestCase):
    def test_tramo_dentro_de_un_trozo(self):
        archivos, desde, dur = tramo(100_000, 10)  # muerte en el segundo 110 de la grabación
        self.assertEqual((archivos, desde, dur), (["r01_seg_000.mkv"], 90.0, clips.ANTES_S + clips.DESPUES_S))

    def test_tramo_entre_dos_trozos(self):
        archivos, desde, _ = tramo(305_000, 5)  # segundo 310: empieza en el 290 del primer trozo
        self.assertEqual(archivos, ["r01_seg_000.mkv", "r01_seg_001.mkv"])
        self.assertEqual(desde, 290.0)

    def test_al_principio_no_empieza_antes_de_cero(self):
        archivos, desde, dur = tramo(5_000, 2)
        self.assertEqual((archivos, desde), (["r01_seg_000.mkv"], 0.0))
        self.assertEqual(dur, 7 + clips.DESPUES_S)

    def test_orden_con_dos_trozos_usa_concat(self):
        orden = clips.orden_ffmpeg("ffmpeg", [Path("a.mkv"), Path("b.mkv")], 290.0, 24, Path("x.mp4"), Path("x.txt"))
        self.assertIn("concat", orden)
        self.assertEqual(orden[-1], "x.mp4")

    def test_sin_grabacion_no_hay_recorte(self):
        self.assertIsNone(clips.recortar("ffmpeg", Path("no-existe"), 0, {"ms": 60_000, "t": "1:00"}, 10))

    # ffmpeg se relanzó a los 10:00 de partida (la serie 1 empezó 30 s antes del 0:00).
    SERIES = {1: 30, 2: -600}

    def test_cada_muerte_en_su_serie(self):
        self.assertEqual(clips.tramo(300_000, self.SERIES), (["r01_seg_001.mkv"], 10.0, 24.0))  # 5:00 -> 5:30 de r01
        self.assertEqual(clips.tramo(720_000, self.SERIES), (["r02_seg_000.mkv"], 100.0, 24.0))  # 12:00 -> 2:00 de r02
        self.assertEqual(tramo(1_498_000, self.SERIES)[0], ["r02_seg_002.mkv", "r02_seg_003.mkv"])  # 24:58

    def test_justo_despues_de_relanzar_empieza_con_la_serie(self):
        archivos, desde, dur = tramo(605_000, self.SERIES)  # 10:05: 5 s después de empezar r02
        self.assertEqual((archivos, desde, dur), (["r02_seg_000.mkv"], 0.0, 5 + clips.DESPUES_S))

    def test_antes_de_que_empiece_la_grabacion_no_hay_tramo(self):
        self.assertIsNone(clips.tramo(5_000, {1: -10}))  # se empezó a grabar a los 0:10
        self.assertIsNone(clips.tramo(5_000, None))
        self.assertIsNone(clips.recortar("ffmpeg", Path("no-existe"), 0, {"ms": 5_000, "t": "0:05"}, {1: -10}))

    def test_lista_de_concat_con_comillas(self):
        rutas = [Path("C:/Users/O'Neill/Vídeos/LoL-coach/a.mkv"), Path("C:/x/b.mkv")]
        texto = clips.lista_concat(rutas)
        self.assertEqual(texto.splitlines()[0], "file 'C:/Users/O'\\''Neill/Vídeos/LoL-coach/a.mkv'")
        self.assertEqual([leer_concat(linea) for linea in texto.splitlines()], [r.as_posix() for r in rutas])

    def test_recorta_de_la_serie_buena_aunque_la_ruta_lleve_comilla(self):
        with tempfile.TemporaryDirectory() as d:
            carpeta = Path(d) / "O'Neill" / "2026-11-06_partida1"
            carpeta.mkdir(parents=True)
            for nombre in ("r01_seg_000.mkv", "r01_seg_001.mkv", "r02_seg_000.mkv", "r02_seg_001.mkv"):
                (carpeta / nombre).write_bytes(b"x")
            vistas = []

            def ffmpeg_falso(orden, **kw):
                lista = Path(orden[orden.index("-i") + 1])
                vistas.append([leer_concat(linea) for linea in lista.read_text(encoding="utf-8").splitlines()])
                Path(orden[-1]).write_bytes(b"mp4")

            muerte = {"ms": 898_000, "t": "14:58"}  # 4:58 de r02: el recorte une sus dos primeros trozos
            with mock.patch.object(clips.subprocess, "run", ffmpeg_falso):
                ruta = clips.recortar("ffmpeg", carpeta, 2, muerte, self.SERIES)
            self.assertEqual(ruta, carpeta / "muertes" / "03_14-58.mp4")
            self.assertEqual(vistas, [[(carpeta / "r02_seg_000.mkv").as_posix(), (carpeta / "r02_seg_001.mkv").as_posix()]])
            self.assertEqual([p.name for p in (carpeta / "muertes").iterdir()], ["03_14-58.mp4"])  # sin la lista


def leer_concat(linea):
    """La ruta de una línea «file ...» tal y como la lee ffmpeg: entre '' todo va tal cual y fuera, \\ escapa."""
    palabra, _, resto = linea.partition(" ")
    assert palabra == "file"
    ruta, i, entre_comillas = [], 0, False
    while i < len(resto):
        c = resto[i]
        if c == "'":
            entre_comillas = not entre_comillas
        elif c == "\\" and not entre_comillas:
            i += 1
            ruta.append(resto[i])
        else:
            ruta.append(c)
        i += 1
    return "".join(ruta)


if __name__ == "__main__":
    unittest.main()
