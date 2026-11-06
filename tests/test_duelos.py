"""Pruebas del duelo contra el rival directo: extracción de registros, análisis y base."""

import gzip
import json
import unittest
from pathlib import Path

from deepprep import analisis as an
from deepprep import duelos as du
from deepprep.base_duelos import BaseDuelos

DATOS = Path(__file__).parent / "datos"


def cargar(nombre):
    with gzip.open(DATOS / nombre, "rt", encoding="utf-8") as f:
        return json.load(f)


def registro(g, peleas=(), m10=0, oro10=0, dur=28.0, cs10=70, ka10=2, larvas=1, drag1=0, item=(3100, 10.0), muertes=()):
    return {
        "pos": "JUNGLE",
        "a": 131,
        "b": 64,
        "g": int(g),
        "dur": dur,
        "v": "16.20",
        "dif": {"10": [oro10, 0, 0]},
        "cs10": cs10,
        "peleas": [list(p) for p in peleas],
        "muertes": [list(m) for m in muertes],
        "m10": m10,
        "ka10": ka10,
        "item": list(item),
        "runa": [8010, 8300],
        "hab": "QWE>QWE",
        "larvas": larvas,
        "drag1": drag1,
    }


class Extraccion(unittest.TestCase):
    def test_diez_registros_simetricos(self):
        regs = du.extraer(cargar("partida.json.gz"), cargar("linea.json.gz"), legendarios={3100, 6653, 3157, 4645, 3089})
        self.assertEqual(len(regs), 10)
        por = {(r["pos"], r["a"]): r for r in regs}
        for r in regs:
            otro = por[(r["pos"], r["b"])]
            self.assertEqual(r["g"] + otro["g"], 1)
            self.assertEqual(r["dif"]["10"], [-x for x in otro["dif"]["10"]])
            # La misma pelea vista desde los dos lados: uno la gana y el otro la pierde.
            self.assertEqual(len(r["peleas"]), len(otro["peleas"]))
            self.assertEqual(sum(p[3] for p in r["peleas"]) + sum(p[3] for p in otro["peleas"]), len(r["peleas"]))
            self.assertTrue(all(len(p) == 8 for p in r["peleas"]))
        jungla = [r for r in regs if r["pos"] == "JUNGLE"]
        self.assertTrue(all("larvas" in r and "drag1" in r for r in jungla))

    def test_descarta_partidas_cortas(self):
        partida = cargar("partida.json.gz")
        partida["info"]["gameDuration"] = 600
        self.assertEqual(du.extraer(partida, cargar("linea.json.gz"), set()), [])


class Analisis(unittest.TestCase):
    def test_pocos_datos(self):
        r = du.analizar([registro(True)] * 5, [], "Diana", "Nidalee", "JUNGLE")
        self.assertTrue(r["poco"])
        self.assertEqual(r["datos"], [])

    def test_peleas_por_nivel_y_lo_que_hacen_los_que_ganan(self):
        # Antes del 6 pierde casi todas las peleas, después las gana; las que ganan mueren menos antes del 10.
        antes = [(4.0, 4, 4, 0, 2, "jungla", "sup", True)] * 3 + [(4.5, 5, 4, 1, 2, "rio", "sup", True)]
        despues = [(9.0, 7, 6, 1, 2, "rio", "inf", False)] * 3
        regs = [registro(True, antes[:1] + despues, m10=0, oro10=600) for _ in range(12)]
        regs += [registro(False, antes, m10=3, oro10=-600, muertes=[(4.0, 1, "jungla", "sup", True)] * 2) for _ in range(12)]
        r = du.analizar(
            regs,
            [registro(False, antes, m10=2)] * 4,
            "Diana",
            "Nidalee",
            "JUNGLE",
            nombre_objeto=lambda i: f"O{i}",
            nombre_runa=lambda i: f"R{i}",
        )
        textos = " | ".join(d["texto"] for d in r["datos"])
        self.assertIn("Diana gana el 20% de las peleas con Nidalee antes de su 6; desde el 6, el 100%.", textos)
        self.assertIn("Peleas con Nidalee antes del 6: 1,0 en las que gana Diana, 4,0 en las que pierde.", textos)
        self.assertIn("tu jungla de arriba", textos)
        self.assertLessEqual(len(r["datos"]), 4)
        self.assertEqual((r["build"]["runa"], r["build"]["objeto"], r["build"]["maximiza"]), ("R8010", "O3100", "Q > W > E"))
        c = du.comparar([registro(False, antes, m10=2)] * 4, [x for x in regs if x["g"]], "JUNGLE", "Ganan este duelo")
        assert c is not None
        tu = {f["que"]: f for f in c["filas"]}
        self.assertEqual((c["ref"], c["n"], c["n_ref"]), ("Ganan este duelo", 4, 12))
        self.assertEqual(
            (tu["Muertes antes del 10"]["tu"], tu["Muertes antes del 10"]["ref"], tu["Muertes antes del 10"]["mejor"]),
            ("2,0", "0,0", False),
        )
        self.assertIsNone(tu["Peleas con tu rival antes del 6"]["mejor"])
        self.assertIsNone(du.comparar([registro(True)], [registro(True)] * 2, "JUNGLE", "X"))  # referencia con muy pocas partidas

    def test_habitos_segun_la_posicion(self):
        def reg(g, cs):
            return dict(registro(g), pos="MIDDLE", dif={"10": [0, 0, cs]})

        regs = [reg(True, 15) for _ in range(12)] + [reg(False, -15) for _ in range(12)]
        r = du.analizar(regs, [reg(False, -5)] * 4, "Katarina", "Ahri", "MIDDLE")
        self.assertIn(
            "Diferencia de CS con Ahri al 10: 15,0 en las que gana Katarina, -15,0 en las que pierde.",
            [d["texto"] for d in r["datos"]],
        )
        c = du.comparar([reg(False, -5)] * 4, regs[:12], "MIDDLE", "Faker")
        assert c is not None
        self.assertIn({"que": "CS sobre tu rival al 10", "tu": "-5", "ref": "+15", "mejor": False}, c["filas"])
        apoyo = du.comparar(regs, regs, "UTILITY", "X")
        assert apoyo is not None
        self.assertNotIn("CS al 10", [f["que"] for f in apoyo["filas"]])
        self.assertFalse(any("Larvas" in d["texto"] or "dragón" in d["texto"] for d in r["datos"]))
        en_mid = [dict(x, muertes=[[5.0, 1, "mid", "sup", True]] * 2) for x in regs]
        self.assertFalse(
            any("muertes de Katarina" in d["texto"] for d in du.analizar(en_mid, [], "Katarina", "Ahri", "MIDDLE")["datos"])
        )
        sup = du.analizar([dict(x, pos="UTILITY") for x in regs], [], "Thresh", "Nautilus", "UTILITY")
        self.assertFalse(any("CS" in d["texto"] for d in sup["datos"]))

    def test_ningun_texto_da_ordenes(self):
        codigo = Path(du.__file__).read_text(encoding="utf-8").lower()
        for orden in ("evita", "no pelees", "debes", "tienes que", "juega "):
            self.assertNotIn(orden, codigo)


class Seleccion(unittest.TestCase):
    ROLES = {
        64: {"JUNGLE": 0.9, "TOP": 0.1},
        103: {"MIDDLE": 1.0},
        222: {"BOTTOM": 1.0},
        412: {"UTILITY": 1.0},
        266: {"TOP": 1.0},
    }

    def test_rival_probable(self):
        self.assertEqual(an.rival_probable([103, 64], "JUNGLE", self.ROLES), 64)
        self.assertIsNone(an.rival_probable([103, 222], "JUNGLE", self.ROLES))
        self.assertEqual(an.rival_probable([266, 64, 103, 222, 412], "TOP", self.ROLES), 266)


class Base(unittest.TestCase):
    def test_guardar_y_leer(self):
        b = BaseDuelos(":memory:")
        b.guardar("EUW1_1", [dict(registro(True), puuid="yo")])
        b.guardar("EUW1_2", [dict(registro(False), puuid="otro")])
        self.assertTrue(b.vista("EUW1_1"))
        self.assertEqual(len(b.duelo(131, "JUNGLE", 64)), 2)
        self.assertEqual(len(b.duelo(131, "JUNGLE", 64, excluir={"yo"})), 1)
        self.assertEqual(len(b.de({"yo"}, 131, "JUNGLE")), 1)
        self.assertEqual(b.resumen(), {"partidas": 2, "miradas": 2})

    def test_pool(self):
        def m(i, campeon, pos):
            return {"id": str(i), "remake": False, "jug": [{"puuid": "yo", "campeon": campeon, "pos": pos}]}

        partidas = [m(i, 131, "JUNGLE") for i in range(6)] + [m(10 + i, 11, "JUNGLE") for i in range(2)]
        self.assertEqual(an.pool_de(partidas, {"yo"}), [(131, "JUNGLE")])


if __name__ == "__main__":
    unittest.main()
