"""Revisión post-partida con la clasificatoria real de tests/datos (Diana contra Master Yi, 12/10/2026)."""

import gzip
import json
import unittest
from pathlib import Path

from deepprep import analisis as an
from deepprep import revision as rv
from deepprep.tipos import Json, Jugador, Linea, Partida

DATOS = Path(__file__).parent / "datos"


def revisar(*args, **kw) -> Json:
    """rv.revisar, que en estas pruebas siempre encuentra al jugador."""
    r = rv.revisar(*args, **kw)
    assert r is not None
    return r


def cargar(nombre):
    with gzip.open(DATOS / nombre, "rt", encoding="utf-8") as f:
        return json.load(f)


class Revision(unittest.TestCase):
    partida: Partida
    linea: Linea
    yo: Jugador

    @classmethod
    def setUpClass(cls):
        cls.partida = an.reducir_partida(cargar("partida.json.gz"))
        cls.linea = rv.reducir_linea_completa(cargar("linea.json.gz"))
        cls.yo = next(j for j in cls.partida["jug"] if j["campeon"] == 131)  # Diana

    def test_muertes_objetivos_y_comparacion(self):
        r = revisar(self.partida, self.linea, self.yo["puuid"], lambda c: f"C{c}", desfase_s=20)
        json.dumps(r)
        self.assertEqual(len(r["muertes"]), self.yo["d"])
        self.assertEqual(r["kda"], [self.yo["k"], self.yo["d"], self.yo["a"]])
        m = r["muertes"][0]
        self.assertTrue(m["donde"].startswith("en "))
        self.assertGreaterEqual(m["rivales"], 1)
        self.assertTrue(m["video"]["archivo"].startswith("r01_seg_"))
        self.assertTrue(r["objetivos"])
        self.assertEqual(set(r["comparacion"]["minutos"]), {"10", "15"})
        oro_mio, oro_suyo = r["comparacion"]["minutos"]["10"]["oro"]
        self.assertGreater(oro_mio, 0)
        self.assertGreater(oro_suyo, 0)

    def test_prevision_contra_lo_que_paso(self):
        panel = {"gank": {"linea": "top", "veces": 3, "n": 5}, "lineas": [{"linea": "bot", "veredicto": "Aquí se equivocan"}]}
        r = revisar(self.partida, self.linea, self.yo["puuid"], str, panel=panel)
        temas = [f["tema"] for f in r["prevision"]]
        self.assertEqual(temas, ["Primer gank del jungla rival", "Rival de bot con más errores"])
        self.assertTrue(all(isinstance(f["acierto"], bool) for f in r["prevision"]))

    def test_en_otra_posicion_se_compara_con_tu_rival_de_linea(self):
        adc = next(j for j in self.partida["jug"] if j["pos"] == "BOTTOM" and j["equipo"] == self.yo["equipo"])
        rival = next(j for j in self.partida["jug"] if j["pos"] == "BOTTOM" and j["equipo"] != adc["equipo"])
        r = revisar(self.partida, self.linea, adc["puuid"], lambda c: f"C{c}")
        self.assertEqual(r["comparacion"]["rival"], f"C{rival['campeon']}")

    def test_sin_estar_en_la_partida(self):
        self.assertIsNone(rv.revisar(self.partida, self.linea, "nadie", str))

    def test_muertes_de_despues_de_relanzar_ffmpeg(self):
        relanzado = min(m["ms"] for m in revisar(self.partida, self.linea, self.yo["puuid"], str)["muertes"]) + 1000
        series = {1: 20, 2: -relanzado / 1000}  # la serie 2 empieza justo después de la primera muerte
        r = revisar(self.partida, self.linea, self.yo["puuid"], str, desfase_s=series)
        primera, *resto = r["muertes"]
        self.assertTrue(primera["video"]["archivo"].startswith("r01_seg_"))
        self.assertTrue(resto)
        self.assertTrue(all(m["video"]["archivo"].startswith("r02_seg_") for m in resto))


class Video(unittest.TestCase):
    def test_trozos_de_cinco_minutos(self):
        self.assertEqual(rv.en_video(0, 14), {"archivo": "r01_seg_000.mkv", "en": "0:14"})
        self.assertEqual(rv.en_video(10 * 60_000, 14), {"archivo": "r01_seg_002.mkv", "en": "0:14"})
        self.assertIsNone(rv.en_video(1000, None))

    def test_lo_de_despues_de_relanzar_ffmpeg_va_en_su_serie(self):
        series = {1: 30, 2: -600}  # la serie 2 empezó a los 10:00 de partida
        self.assertEqual(rv.en_video(9 * 60_000, series), {"archivo": "r01_seg_001.mkv", "en": "4:30"})
        self.assertEqual(rv.en_video(12 * 60_000, series), {"archivo": "r02_seg_000.mkv", "en": "2:00"})
        self.assertEqual(rv.en_grabacion(10 * 60_000, series), (2, 0.0))
        self.assertIsNone(rv.en_video(0, {1: -5}))  # aún no se grababa


class Tendencias(unittest.TestCase):
    def test_sesiones_franjas_y_junglas(self):
        def partida(i, gana, hora, rival=64):
            yo = {"puuid": "yo", "pid": 2, "equipo": 100, "campeon": 131, "pos": "JUNGLE", "gana": gana}
            otro = {"puuid": "r", "pid": 7, "equipo": 200, "campeon": rival, "pos": "JUNGLE", "gana": not gana}
            # Cada partida empieza 40 minutos después de la anterior: todas en la misma sesión.
            return {
                "id": f"m{i}",
                "creacion": i * 2_400_000,
                "duracion": 1500,
                "cola": 420,
                "mapa": 11,
                "remake": False,
                "hora": hora,
                "jug": [yo, otro],
            }

        lista = [partida(0, True, 21), partida(1, False, 22), partida(2, False, 23), partida(3, True, 10)]
        horas = {m["creacion"]: m["hora"] for m in lista}
        t = rv.tendencias(list(reversed(lista)), {"yo"}, lambda c: f"C{c}", lambda ms: horas[ms])
        assert t is not None
        sesion = {f["nombre"]: (f["v"], f["n"]) for f in t["sesion"]}
        self.assertEqual(sesion["Primera partida de la sesión"], (1, 1))
        self.assertEqual(sesion["Después de ganar"], (0, 1))
        self.assertEqual(sesion["Después de perder"], (1, 2))
        franjas = {f["nombre"]: f["n"] for f in t["franjas"]}
        self.assertEqual(franjas, {"Mañana (6-14 h)": 1, "Noche (20-24 h)": 3})
        self.assertEqual(t["rivales"][0], {"nombre": "C64", "n": 4, "v": 2, "campeon": 64})
        # Con varias posiciones se dice en cuál fue cada duelo.
        adc = dict(
            lista[0],
            id="m9",
            jug=[dict(lista[0]["jug"][0], pos="BOTTOM", campeon=29), dict(lista[0]["jug"][1], pos="BOTTOM", campeon=22)],
        )
        t = rv.tendencias([*list(reversed(lista)), adc], {"yo"}, lambda c: f"C{c}", lambda ms: 12)
        assert t is not None
        self.assertEqual({f["nombre"] for f in t["rivales"]}, {"C64 (jungla)", "C22 (ADC)"})
        self.assertIsNone(rv.tendencias([], {"yo"}, str, lambda ms: 0))


if __name__ == "__main__":
    unittest.main()
