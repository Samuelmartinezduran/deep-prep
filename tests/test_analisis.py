"""Pruebas del análisis. Los datos reales son una clasificatoria del 12/10/2026 (Diana contra Master Yi)."""

import gzip
import itertools
import json
import unittest
from collections import Counter
from pathlib import Path

from deepprep import analisis as an
from deepprep.tipos import Jugador, Linea, Partida

DATOS = Path(__file__).parent / "datos"


def cargar(nombre):
    with gzip.open(DATOS / nombre, "rt", encoding="utf-8") as f:
        return json.load(f)


def jug(puuid, equipo, pos, campeon, gana, pid=1, k=0, d=0, a=0, **ch):
    return {
        "puuid": puuid,
        "nombre": puuid,
        "tag": "",
        "pid": pid,
        "equipo": equipo,
        "campeon": campeon,
        "pos": pos,
        "gana": gana,
        "k": k,
        "d": d,
        "a": a,
        "cs": 0,
        "oro": 0,
        "dano": 0,
        "vision": 0,
        "wards": 0,
        "control": 0,
        "s1": 4,
        "s2": 11 if pos == "JUNGLE" else 14,
        "ch": ch,
    }


def partida(id_, jugadores, creacion=0, cola=420, remake=False):
    return {
        "id": id_,
        "creacion": creacion,
        "duracion": 1800,
        "cola": cola,
        "mapa": 11,
        "remake": remake,
        "equipos": {},
        "jug": jugadores,
    }


class Geografia(unittest.TestCase):
    def test_zonas_conocidas(self):
        self.assertEqual(an.zona(3800, 7900), ("jungla", "sup", 100))  # azul del equipo azul
        self.assertEqual(an.zona(7800, 4000), ("jungla", "inf", 100))  # rojo del equipo azul
        self.assertEqual(an.zona(7100, 10900), ("jungla", "sup", 200))  # rojo del equipo rojo
        self.assertEqual(an.zona(11000, 6900), ("jungla", "inf", 200))  # azul del equipo rojo
        self.assertEqual(an.zona(9866, 4414)[:2], ("rio", "inf"))  # foso del dragón
        self.assertEqual(an.zona(5007, 10471)[:2], ("rio", "sup"))  # foso del barón
        self.assertEqual(an.zona(1000, 10000)[0], "top")
        self.assertEqual(an.zona(10000, 1000)[0], "bot")
        self.assertEqual(an.zona(7400, 7400)[0], "mid")
        self.assertEqual(an.zona(600, 600)[0], "base")
        self.assertEqual(an.zona(14300, 14300)[0], "base")

    def test_linea_de_una_kill(self):
        self.assertEqual(an.linea_de_kill(6303, 6564), "mid")
        self.assertEqual(an.linea_de_kill(981, 10441), "top")
        self.assertEqual(an.linea_de_kill(13500, 2500), "bot")
        self.assertEqual(an.linea_de_kill(9837, 4397), "jungla")  # dragón

    def test_lado_del_buff(self):
        self.assertEqual(an.lado_del_buff("azul", 100), "sup")
        self.assertEqual(an.lado_del_buff("rojo", 100), "inf")
        self.assertEqual(an.lado_del_buff("rojo", 200), "sup")
        self.assertEqual(an.lado_del_buff("azul", 200), "inf")


class DatosReales(unittest.TestCase):
    partida: Partida
    linea: Linea
    diana: Jugador
    yi: Jugador

    @classmethod
    def setUpClass(cls):
        cls.partida = an.reducir_partida(cargar("partida.json.gz"))
        cls.linea = an.reducir_linea(cargar("linea.json.gz"))
        cls.diana = next(j for j in cls.partida["jug"] if j["campeon"] == 131)
        cls.yi = next(j for j in cls.partida["jug"] if j["pos"] == "JUNGLE" and j["equipo"] != cls.diana["equipo"])

    def test_reduccion_de_partida(self):
        p = self.partida
        self.assertEqual((p["cola"], p["mapa"], p["remake"], len(p["jug"])), (420, 11, False, 10))
        d = self.diana
        self.assertEqual((d["pos"], d["equipo"], d["gana"], d["k"], d["d"], d["a"]), ("JUNGLE", 200, False, 4, 8, 6))
        self.assertEqual(Counter(j["pos"] for j in p["jug"]), Counter(dict.fromkeys(an.POSICIONES, 2)))
        self.assertIn("enemyJungleMonsterKills", d["ch"])
        self.assertEqual(p["equipos"]["100"]["gana"], True)
        self.assertLess(len(json.dumps(p)), 15000)

    def test_reduccion_de_linea(self):
        l = self.linea
        self.assertEqual(len(l["pos"]["7"]), 16)
        self.assertEqual(l["pids"][self.diana["puuid"]], 7)
        self.assertTrue(all(a[0] <= b[0] for a, b in itertools.pairwise(l["kills"])))
        self.assertIn("DRAGON", {m[1] for m in l["monstruos"]})
        self.assertLess(len(json.dumps(l)), 15000)

    def test_inicio_y_cruce(self):
        # Los dos junglas empezaron en rojo y al 3:00 estaban en el lado contrario.
        self.assertEqual(an.inicio_jungla(self.linea, 7), "rojo")
        self.assertEqual(an.inicio_jungla(self.linea, 2), "rojo")
        self.assertEqual(an.lado_al(self.linea, 7, 3), "inf")
        self.assertEqual(an.lado_al(self.linea, 2, 3), "sup")

    def test_primer_gank_y_muertes(self):
        self.assertEqual(an.primer_gank(self.linea, 7), (367917, "bot"))
        self.assertEqual(an.muertes_antes(self.linea, 7, 15), 3)
        oro_yi, oro_diana = an.oro_al(self.linea, 2, 10), an.oro_al(self.linea, 7, 10)
        assert oro_yi is not None and oro_diana is not None
        self.assertGreater(oro_yi, oro_diana)

    def test_perfil_del_jungla_rival(self):
        perfil = an.perfil_jungla(self.yi["puuid"], [self.partida], {self.partida["id"]: self.linea}, self.yi["campeon"], 100)
        self.assertEqual((perfil["n"], perfil["n_campeon"], perfil["n_lineas"]), (1, 1, 1))
        self.assertEqual(perfil["snowball"]["delante"], [1, 1])
        self.assertEqual(perfil["ganks"], {"bot": 1})
        titulos = [t["titulo"] for t in perfil["tarjetas"]]
        self.assertIn("Primer gank", titulos)
        self.assertIn("Si se adelanta", titulos)
        for t in perfil["tarjetas"]:
            self.assertIn(t["tono"], ("ojo", "bien", "neutro"))

    def test_perfil_sin_partidas_de_jungla(self):
        perfil = an.perfil_jungla("nadie", [self.partida], {}, 1, 100)
        self.assertEqual((perfil["n"], perfil["tarjetas"]), (0, []))


class Roles(unittest.TestCase):
    def test_smite_manda_y_el_resto_sale_del_campeon(self):
        tasas = {
            1: {"MIDDLE": 5},
            2: {"TOP": 5},
            3: {"JUNGLE": 3, "TOP": 1},
            4: {"BOTTOM": 5},
            5: {"UTILITY": 4, "MIDDLE": 1},
        }
        equipo = [
            {"campeon": 4, "s1": 4, "s2": 7, "puuid": "a"},
            {"campeon": 5, "s1": 4, "s2": 3, "puuid": "b"},
            {"campeon": 1, "s1": 4, "s2": 14, "puuid": "c"},
            {"campeon": 3, "s1": 4, "s2": 12, "puuid": "d"},  # campeón de jungla, pero sin smite
            {"campeon": 2, "s1": 11, "s2": 4, "puuid": "e"},  # campeón de top con smite
        ]
        self.assertEqual(an.asignar_roles(equipo, tasas), ["BOTTOM", "UTILITY", "MIDDLE", "TOP", "JUNGLE"])

    def test_el_historial_desempata(self):
        equipo = [{"campeon": 9, "s1": 4, "s2": 14, "puuid": p} for p in "abcd"] + [
            {"campeon": 9, "s1": 11, "s2": 4, "puuid": "e"}
        ]
        hist = {"a": Counter(UTILITY=9), "b": Counter(TOP=9), "c": Counter(BOTTOM=9), "d": Counter(MIDDLE=9)}
        self.assertEqual(an.asignar_roles(equipo, {}, hist), ["UTILITY", "TOP", "BOTTOM", "MIDDLE", "JUNGLE"])

    def test_equipo_incompleto(self):
        self.assertEqual(an.asignar_roles([{"campeon": 1}], {}), [""])


class Resumen(unittest.TestCase):
    def muestra(self, resultados, pos="TOP", campeon=10):
        return [
            partida(
                f"m{i}", [jug("yo", 100, pos, campeon, g, k=5, d=2, a=3), jug("otro", 200, pos, 20, not g)], creacion=1000 - i
            )
            for i, g in enumerate(resultados)
        ]

    def test_racha_y_campeon(self):
        res = an.resumen_jugador("yo", self.muestra([True, True, True, False, True]), 10)
        self.assertEqual((res["n"], res["v"], res["racha_actual"]), (5, 4, 3))
        self.assertEqual((res["camp"]["n"], res["camp"]["v"]), (5, 4))
        self.assertEqual(res["kda"], [5, 2, 3])
        res = an.resumen_jugador("yo", self.muestra([False, False, True]), 99)
        self.assertEqual((res["racha_actual"], res["camp"]["n"], res["camp"]["kda"]), (-2, 0, None))

    def test_no_cuenta_remakes_ni_otros_mapas(self):
        m = self.muestra([True, True])
        m[0]["remake"] = True
        m[1]["cola"] = 450
        self.assertEqual(an.resumen_jugador("yo", m, 10)["n"], 0)

    def test_ventaja_de_linea_propia_y_del_rival(self):
        campo = an.CAMPO_LINEA
        m = [
            partida("a", [jug("yo", 100, "TOP", 1, True, **{campo: 1}), jug("r", 200, "TOP", 2, False, **{campo: 0})]),
            partida("b", [jug("yo", 100, "TOP", 1, False, **{campo: 0}), jug("r", 200, "TOP", 2, True, **{campo: 1})]),
            partida("c", [jug("yo", 100, "TOP", 1, False, **{campo: 0}), jug("r", 200, "TOP", 2, True, **{campo: 0})]),
        ]
        self.assertEqual(an.resumen_jugador("yo", m, 1)["linea"], {"n": 3, "v": 1, "d": 1})

    def test_fuera_de_rol(self):
        res = an.resumen_jugador("yo", self.muestra([True] * 10, pos="TOP"), 10)
        self.assertTrue(an.fuera_de_rol(res, "UTILITY"))
        self.assertFalse(an.fuera_de_rol(res, "TOP"))
        self.assertFalse(an.fuera_de_rol(an.resumen_jugador("yo", self.muestra([True] * 3), 10), "UTILITY"))

    def test_etiquetas(self):
        ahora = 1_800_000_000_000
        res = an.resumen_jugador("yo", self.muestra([True] * 9), 10)
        nombres = [e["t"] for e in an.etiquetas(res, "TOP", {"championPoints": 500000, "lastPlayTime": ahora}, ahora)]
        self.assertEqual(nombres, ["OTP", "Racha +9"])
        res = an.resumen_jugador("yo", self.muestra([False] * 9), 99)
        nombres = [e["t"] for e in an.etiquetas(res, "MIDDLE", {"championPoints": 900}, ahora)]
        self.assertEqual(nombres, ["Primera vez", "Fuera de rol", "Racha -9"])
        res = an.resumen_jugador("yo", self.muestra([True, False]), 10)
        viejo = {"championPoints": 80000, "lastPlayTime": ahora - 45 * 86400000}
        self.assertEqual([e["t"] for e in an.etiquetas(res, "TOP", viejo, ahora)], ["Oxidado"])
        # En una cuenta recién hecha, tener poca maestría con el campeón no cuenta como estreno.
        nueva = {"championPoints": 900, "total": 60000}
        self.assertEqual([e["t"] for e in an.etiquetas(res, "TOP", nueva, ahora)], ["Cuenta nueva"])
        self.assertEqual(
            [e["t"] for e in an.etiquetas(res, "TOP", {"championPoints": 900, "total": 3000000}, ahora)], ["Poco rodado"]
        )

    def test_premade_con_dos_partidas_juntos(self):
        juntos = [partida(f"m{i}", [jug("a", 100, "TOP", 1, True), jug("b", 100, "MIDDLE", 2, True)]) for i in range(2)]
        una = [partida("x", [jug("c", 100, "TOP", 1, True), jug("d", 100, "MIDDLE", 2, True)])]
        rivales = [partida(f"r{i}", [jug("a", 100, "TOP", 1, True), jug("e", 200, "TOP", 2, False)]) for i in range(3)]
        grupos = an.premades(["a", "b", "c", "d", "e"], {"a": juntos + rivales, "c": una})
        self.assertEqual(grupos, {"a": 1, "b": 1})


class Lineas(unittest.TestCase):
    def test_ordena_por_lo_que_falla_el_rival(self):
        campo = an.CAMPO_LINEA

        def res(pos, gana_linea):
            m = [
                partida(
                    f"{pos}{i}",
                    [
                        jug("p", 100, pos, 1, gana_linea, **{campo: int(gana_linea)}),
                        jug("r", 200, pos, 2, not gana_linea, **{campo: int(not gana_linea)}),
                    ],
                )
                for i in range(8)
            ]
            return an.resumen_jugador("p", m, 1)

        def lado(top, mid, bot):
            return {
                pos: {"nombre": pos, "campeon": pos.capitalize(), "res": res(pos, g), "primera_vez": False}
                for pos, g in (("TOP", top), ("MIDDLE", mid), ("BOTTOM", bot), ("UTILITY", bot))
            }

        orden = an.lineas_de_juego(lado(True, True, True), lado(True, True, False))
        self.assertEqual(orden[0]["linea"], "bot")
        self.assertEqual((orden[0]["veredicto"], orden[0]["tono"]), ("Aquí se equivocan", "bien"))
        self.assertTrue(any("ventaja clara" in m for m in orden[0]["rival"]))
        sufre = an.lineas_de_juego(lado(False, True, True), lado(True, True, True))
        top = next(l for l in sufre if l["linea"] == "top")
        self.assertEqual(top["tono"], "ojo")


class Historial(unittest.TestCase):
    def test_cruces_y_conocidos(self):
        dia = 86400000
        ahora = 100 * dia
        mias = [
            # Diana jungla contra Yi jungla: una derrota y una victoria.
            partida(
                "a",
                [jug("yo", 100, "JUNGLE", 131, False), jug("x", 200, "JUNGLE", 11, True), jug("z", 200, "TOP", 50, True)],
                creacion=ahora - 2 * dia,
            ),
            partida("b", [jug("yo", 200, "JUNGLE", 131, True), jug("y", 100, "JUNGLE", 11, False)], creacion=ahora - 5 * dia),
            # Yi rival, pero en top: no cuenta como duelo de junglas.
            partida("c", [jug("yo", 100, "JUNGLE", 64, True), jug("y", 200, "TOP", 11, False)], creacion=ahora - 9 * dia),
            # Yi en mi equipo: no es un cruce.
            partida("d", [jug("yo", 100, "JUNGLE", 131, True), jug("w", 100, "TOP", 11, True)], creacion=ahora - 10 * dia),
        ]
        rivales = [
            {"campeon": 11, "pos": "JUNGLE", "nombre_campeon": "Master Yi"},
            {"campeon": 99, "pos": "TOP", "nombre_campeon": "Lux"},
        ]
        h = an.mi_historial({"yo"}, mias, 131, rivales, {"x": "Equis", "nuevo": "Nuevo"}, ahora, mi_pos="JUNGLE")
        self.assertEqual(h["n"], 4)
        self.assertEqual((h["campeon"]["n"], h["campeon"]["v"]), (3, 2))
        self.assertEqual(h["vs_directo"], {"nombre": "Master Yi", "pos": "jungla", "n": 2, "v": 1, "n_mio": 2, "v_mio": 1})
        # Si juegas top, tu duelo directo es el de top (Yi en top en la partida c).
        top = an.mi_historial(
            {"yo"}, mias, 64, [{"campeon": 11, "pos": "TOP", "nombre_campeon": "Master Yi"}], {}, ahora, mi_pos="TOP"
        )
        self.assertEqual((top["vs_directo"]["pos"], top["vs_directo"]["n"]), ("top", 0))
        yi = next(f for f in h["vs"] if f["campeon"] == 11)
        self.assertEqual((yi["n"], yi["v"], yi["n_mio"], yi["v_mio"]), (3, 2, 2, 1))
        self.assertEqual(h["vs"][-1]["campeon"], 99)  # sin cruces, al final
        self.assertEqual(h["conocidos"], [{"nombre": "Equis", "contigo": False, "ganaste": False, "dias": 2, "veces": 1}])

    def test_sin_partidas(self):
        h = an.mi_historial({"yo"}, [], 131, [], {}, 0)
        self.assertEqual((h["n"], h["campeon"], h["vs"]), (0, None, []))


if __name__ == "__main__":
    unittest.main()
