"""La interfaz nativa (deepprep/nativa): lo que pinta cada vista (vistas.py), el gráfico de oro (oro.py), la barra de la
ventana (marco.py) y el puente con la app (puente.py). Son las mismas pruebas que las del panel web (tests/js), en
Python, más las de lo nuevo.

Lo de Qt (marco, puente) solo se prueba si PySide6 está instalado; vistas.py y oro.py no dependen de Qt.
"""

import copy
import importlib.util
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from deepprep import analisis, config
from deepprep.demo import AppDemo, leer
from deepprep.nativa import oro, vistas

HAY_QT = importlib.util.find_spec("PySide6") is not None
QML = Path(vistas.__file__).resolve().parent / "qml" / "DeepPrep"


def demo(caso: unittest.TestCase, **opciones) -> AppDemo:
    """La app de la demo con su carpeta temporal, que se borra al acabar la prueba."""
    carpeta = tempfile.TemporaryDirectory(prefix="deepprep-prueba-")
    caso.addCleanup(carpeta.cleanup)
    return AppDemo(Path(carpeta.name), **opciones)


def panel_aram() -> dict:
    """El panel de ejemplo como el de una ARAM: sin posiciones ni nada de la Grieta (como lo monta la sesión)."""
    p = copy.deepcopy(leer("panel.json"))
    p.update(cola="ARAM", modo="aram", completo=False, jungla=None, rival_linea=None, lineas=[], gank=None, historial=None)
    p.update(plan=[], duelo=None, avisos=[{"tono": "ojo", "texto": "Rivales con mucha maestría en su campeón: Leona."}])
    for f in p["equipos"]["aliado"] + p["equipos"]["rival"]:
        f.update(rol="", rol_txt="", muestra={"n": 0, "v": 0}, camp={"n": 0, "v": 0, "kda": None}, racha=[])
    return p


class OroDeLaPartida(unittest.TestCase):
    def test_diferencia_desde_tu_equipo(self):
        est = {"1": [[500, 0, 0, 1], [1500, 0, 0, 2]], "6": [[500, 0, 0, 1], [1000, 0, 0, 2]]}
        equipo_de = {1: 100, 6: 200}
        self.assertEqual(analisis.diferencia_oro(est, equipo_de, 100), [0, 500])
        self.assertEqual(analisis.diferencia_oro(est, equipo_de, 200), [0, -500])

    def test_cada_revision_la_guarda(self):
        app = demo(self)
        lista = app.revisiones()["lista"]
        r = app.revision(lista[0]["id"])
        assert r is not None
        linea = leer("linea.json")
        self.assertEqual(len(r["dif_oro"]), max(len(v) for v in linea["est"].values()))
        self.assertEqual(r["dif_oro"][0], 0)  # al empezar, todos con el mismo oro
        otra = app.revision(lista[1]["id"])  # la misma partida vista desde el otro equipo
        assert otra is not None
        self.assertEqual(otra["dif_oro"], [-x for x in r["dif_oro"]])

    def test_el_ultimo_punto_va_al_final_de_la_partida(self):
        self.assertEqual(oro.puntos([0, 100, 300], 1.5), [(0.0, 0.0), (1.0, 100.0), (1.5, 300.0)])

    def test_los_tramos_se_cortan_en_el_cero(self):
        arriba, abajo = oro.tramos([(0.0, 0.0), (1.0, 150.0), (2.0, -200.0), (3.0, -100.0)])
        self.assertEqual((len(arriba), len(abajo)), (1, 1))
        self.assertAlmostEqual(arriba[0][-1][0], 1 + 150 / 350)
        self.assertEqual(arriba[0][-1][1], 0.0)
        self.assertEqual(abajo[0][0], arriba[0][-1])  # el tramo de abajo empieza donde acaba el de arriba
        self.assertEqual(abajo[0][-1], (3.0, -100.0))

    def test_las_areas_se_cierran_contra_el_cero(self):
        self.assertEqual(
            oro.areas([[(1.0, 0.0), (2.0, 300.0), (3.0, 100.0)]]),
            [[(1.0, 0.0), (1.0, 0.0), (2.0, 300.0), (3.0, 100.0), (3.0, 0.0)]],
        )

    def test_la_escala_se_ajusta_a_la_partida(self):
        self.assertEqual(oro.escala(-11400, 1500), (-15000, 5000, 5000))  # la partida de la demo
        self.assertEqual(oro.escala(0, 2300), (-1000, 3000, 1000))
        self.assertEqual(oro.escala(0, 0), (-500, 500, 500))  # siempre algo a cada lado del 0
        abajo, arriba, paso = oro.escala(-3000, 45_000)
        self.assertLessEqual((arriba - abajo) / paso, oro.TRAMOS)
        self.assertGreaterEqual(arriba, 45_000)
        abajo, arriba, paso = oro.escala(-90_000, 90_000)  # más de lo que cabe: con el paso más grande
        self.assertEqual(paso, oro.PASOS[-1])
        self.assertLessEqual(abajo, -90_000)

    def test_miles_con_coma_y_signo(self):
        self.assertEqual(oro.k(12_400), "+12,4k")
        self.assertEqual(oro.k(-800), "−0,8k")
        self.assertEqual(oro.k(5000), "+5k")
        self.assertEqual(oro.k(10_000), "+10k")
        self.assertEqual(oro.k(0), "0")
        self.assertEqual(oro.k(-2500, signo=False), "2,5k")

    def test_grafico_de_una_partida(self):
        g = oro.grafico(
            [0, 400, -900, -2100],
            "2:30",
            [{"t": "1:10", "nombre": "Dragón", "tuyo": True, "participaste": False}],
            [{"t": "2:05", "asesino": "Talon", "perdido": "Heraldo rival 0:40 después"}],
        )
        self.assertEqual(g["fin"], 2.5)
        self.assertEqual((g["abajo"], g["arriba"]), (-3000, 1000))
        self.assertEqual([m["txt"] for m in g["marcas_y"]], ["+1k", "0", "−1k", "−2k", "−3k"])
        self.assertEqual(g["puntos"][-1], [2.5, -2100.0, "−2,1k"])
        self.assertEqual(g["final"], {"v": -2100.0, "txt": "−2,1k"})
        self.assertEqual((len(g["tramos_arriba"]), len(g["tramos_abajo"])), (1, 1))
        self.assertAlmostEqual(g["objetivos"][0]["t"], 1 + 10 / 60)
        self.assertTrue(g["muertes"][0]["cara"])


class Piezas(unittest.TestCase):
    def test_cifras(self):
        self.assertEqual(vistas.pct(1, 3), 33)
        self.assertEqual(vistas.pct(1, 2), 50)
        self.assertEqual(vistas.pct(5, 8), 63)  # 62,5: el .5 hacia arriba, como Math.round
        self.assertEqual(vistas.pct(3, 0), 0)
        self.assertEqual(
            (vistas.clase_wr(4, 4), vistas.clase_wr(7, 10), vistas.clase_wr(3, 10), vistas.clase_wr(5, 10)),
            ("", "bien", "mal", ""),
        )
        self.assertEqual((vistas.miles(999), vistas.miles(1500), vistas.miles(486915)), ("999", "2k", "487k"))
        self.assertEqual(vistas.coma(7.8), "7,8")
        self.assertEqual(
            (vistas.numero("−150"), vistas.numero("6,8"), vistas.numero("64%"), vistas.numero("+240")), (-150, 6.8, 64, 240)
        )
        self.assertTrue(vistas.numero("—") != vistas.numero("—"))  # nan

    def test_lp_y_diferencia_con_signo(self):
        self.assertEqual(vistas.lp(-19), {"txt": "−19 LP", "tono": "mal"})
        self.assertEqual(vistas.lp(21), {"txt": "+21 LP", "tono": "bien"})
        self.assertEqual(vistas.lp(0), {"txt": "±0 LP", "tono": "suave"})
        self.assertEqual(vistas.lp(None)["txt"], "")
        self.assertEqual(vistas.diferencia(58, 64), {"txt": "−6", "tono": "mal"})
        self.assertEqual(vistas.diferencia(3, 3), {"txt": "0", "tono": "suave"})

    def test_teclas_etapa_y_fecha(self):
        self.assertEqual(vistas.teclas("ctrl + tab"), ["CTRL", "TAB"])
        self.assertEqual(vistas.teclas(""), [])
        self.assertEqual(vistas.etapa("juego", {}), "En partida")
        self.assertEqual(vistas.etapa("carga", {}), "Pantalla de carga")
        self.assertEqual(vistas.etapa("previa", {}), "En vivo")
        self.assertEqual(vistas.etapa("juego", {"terminada": True}), "Partida terminada")
        self.assertEqual(vistas.fecha(datetime(2026, 11, 7, 23, 10).timestamp() * 1000), "sáb, 7 nov, 23:10")
        self.assertEqual(vistas.liga({"nivel": "diamond", "rank": "II", "lp": 22}), "Diamante II · 22 LP")
        self.assertEqual(vistas.liga({"nivel": "master", "rank": "I", "lp": 87}), "Maestro · 87 LP")

    def test_imagenes(self):
        self.assertEqual(vistas.imagen("/ddragon/campeon/MasterYi.png"), "image://ddragon/campeon/MasterYi")
        self.assertTrue(vistas.imagen("/img/rango/gold.svg").startswith("file:///"))
        self.assertTrue(vistas.imagen("/img/rango/gold.svg").endswith("/recursos/img/rango/gold.svg"))
        self.assertEqual((vistas.imagen(None), vistas.imagen("https://otra.cosa/x.png")), ("", ""))
        self.assertEqual(vistas.icono_rango("../../x"), "")  # solo el nombre de un nivel

    def test_racha_la_mas_reciente_a_la_derecha(self):
        r = vistas.racha([True, False, False])  # la app la da de la más reciente a la más vieja
        assert r is not None
        self.assertEqual(r["items"], [False, False, True])
        self.assertEqual(r["titulo"], "Últimas 3: 1V 2D, la más reciente a la derecha")
        self.assertIsNone(vistas.racha([]))

    def test_rango_oculto_cargando_sin_rango_y_con_rango(self):
        self.assertEqual(vistas.rango({"oculto": True})["estado"], "oculto")
        self.assertEqual(vistas.rango({"liga": None})["estado"], "cargando")
        sin = vistas.rango({"liga": {"solo": None, "flex": {"txt": "Oro II"}}})
        self.assertEqual(sin["estado"], "sin")
        self.assertIn("Flex Oro II", sin["linea2"])
        con = vistas.rango(
            {"liga": {"solo": {"nivel": "diamond", "txt": "Diamante II", "lp": 22, "v": 141, "d": 127}, "flex": None}}
        )
        self.assertEqual((con["estado"], con["txt"]), ("ok", "Diamante II"))
        self.assertIn("22 LP", con["linea2"])
        self.assertIn("53%", con["linea2"])
        self.assertEqual(con["titulo"], "141V 127D en solo/dúo")
        compacto = vistas.rango(
            {"liga": {"solo": {"nivel": "gold", "txt": "Oro I", "lp": 5, "v": 9, "d": 1}, "flex": {"txt": "x"}}}, True
        )
        self.assertNotIn("%", compacto["linea2"])
        self.assertNotIn("Flex", compacto["linea2"])

    def test_lo_de_la_app_se_escapa_en_el_richtext(self):
        f = vistas.filas_vs([{"n": 3, "v": 1, "n_mio": 1, "v_mio": 0, "nombre": "<b>x</b>", "icono": None}], "Diana<script>")
        self.assertIn("Diana&lt;script&gt;", f["filas"][0]["mio"])
        self.assertNotIn("<script>", f["filas"][0]["mio"])
        self.assertEqual(vistas.b("<i>"), '<span style="font-weight:600;color:#f4f5f6;">&lt;i&gt;</span>')

    def test_filas_vs_con_cruces_y_sin_ellos(self):
        vs = [
            {"n": 7, "v": 1, "n_mio": 1, "v_mio": 0, "nombre": "Talon", "icono": "/ddragon/campeon/Talon.png"},
            {"n": 0, "v": 0, "nombre": "Leona"},
        ]
        f = vistas.filas_vs(vs, "Diana")
        self.assertEqual(len(f["filas"]), 1)
        self.assertIn("1V 6D", f["filas"][0]["total"])
        self.assertIn(vistas.COLOR["mal"], f["filas"][0]["total"])  # 14 %, con 7 partidas
        self.assertEqual(f["sin"], "Sin cruces con Leona.")

    def test_el_nombre_se_copia_con_su_tag_salvo_en_los_perfiles_ocultos(self):
        p = leer("panel.json")
        filas = [vistas.fila(f) for f in p["equipos"]["aliado"]]
        self.assertEqual(filas[1]["riot_id"], "Driftmark#DEMO")
        oculto = vistas.fila({"nombre": "Perfil oculto", "tag": "", "oculto": True, "muestra": {}})
        self.assertEqual(oculto["riot_id"], "")
        sin_tag = vistas.fila({"nombre": "Alguien", "tag": "", "muestra": {}})
        self.assertEqual(sin_tag["riot_id"], "")

    def test_grafico_del_gank_una_barra_por_linea_o_nada(self):
        g = vistas.grafico_gank("min 4:33 · top 4 · mid 1 · bot 2")
        assert g is not None
        self.assertEqual([(x["l"], x["n"], x["ancho"]) for x in g["filas"]], [("top", 4, 1.0), ("mid", 1, 0.25), ("bot", 2, 0.5)])
        self.assertEqual(g["filas"][0]["tip"], "top · 4 de 7")
        self.assertIsNone(vistas.grafico_gank("sin datos"))

    def test_tarjetas_el_grafico_solo_en_la_del_gank_y_sin_compacto(self):
        j = {
            "tarjetas": [
                {"titulo": "Primer gank", "valor": "top 4 · mid 1", "detalle": "d", "tono": ""},
                {"titulo": "Inicio", "valor": "Rojo", "detalle": "x", "tono": "ojo"},
            ]
        }
        t = vistas.tarjetas(j)
        self.assertIsNotNone(t[0]["gank"])
        self.assertIsNone(t[1]["gank"])
        c = vistas.tarjetas(j, compacto=True)
        self.assertIsNone(c[0]["gank"])
        self.assertEqual(c[1]["detalle"], "")


class Duelo(unittest.TestCase):
    def test_tabla_comparacion_desde_el_centro_si_hay_negativos(self):
        t = vistas.tabla_comparacion(
            {
                "ref": "Ganan este duelo",
                "n_ref": 87,
                "filas": [
                    {"que": "Oro al 10", "tu": "−180", "ref": "+240", "mejor": False},
                    {"que": "CS", "tu": "58", "ref": "64", "mejor": None},
                ],
            },
            "Tú: esta partida.",
        )
        assert t is not None
        oro_, cs = t["filas"]
        self.assertTrue(oro_["barras"]["centro"])
        self.assertAlmostEqual(oro_["barras"]["tu"]["x"] + oro_["barras"]["tu"]["ancho"], 0.5)  # la tuya, hacia la izquierda
        self.assertEqual(oro_["barras"]["ref"]["x"], 0.5)
        self.assertEqual(oro_["tu_tono"], "mal")
        self.assertFalse(cs["barras"]["centro"])
        self.assertEqual(cs["barras"]["ref"]["ancho"], 1.0)
        self.assertEqual(cs["tu_tono"], "")
        self.assertEqual(t["pie"], "Tú: esta partida. Ganan este duelo: media de 87 partidas. Se cambia en Ajustes.")
        self.assertIsNone(vistas.tabla_comparacion({"filas": []}, "x"))

    def test_duelo_con_pocas_partidas(self):
        d = vistas.duelo({"a": "Diana", "b": "Talon", "pos": "jungla", "n": 3, "poco": True, "en_pool": False, "tu": None})
        assert d is not None
        self.assertTrue(d["poco"])
        self.assertIsNone(d["wr"])
        self.assertIn("no está entre tus campeones más jugados", d["motivo"])

    def test_duelo_compacto_dos_datos_sin_tablas_ni_build(self):
        p = leer("panel.json")
        d = vistas.duelo(p["duelo"], compacto=True)
        completo = vistas.duelo(p["duelo"])
        assert d is not None and completo is not None
        self.assertEqual(len(d["datos"]), 2)
        self.assertEqual(d["datos"][0]["detalle"], "")
        self.assertIsNone(d["tu"])
        self.assertEqual(d["build"], "")
        self.assertEqual(len(completo["datos"]), len(p["duelo"]["datos"]))
        self.assertIsNotNone(completo["tu"])
        self.assertIn("Electrocutar", completo["build"])


class VistasDeLaDemo(unittest.TestCase):
    def estado(self, escena: str) -> dict:
        app = demo(self)
        app.elegir_escena(escena)
        return app.estado()

    def test_pantalla_de_carga_los_diez_el_duelo_el_mapa_del_jungla_y_el_plan(self):
        e = self.estado("carga")
        p = vistas.partida(e)
        self.assertEqual(p["vista"], "panel")
        d = p["datos"]
        self.assertEqual((len(d["aliado"]), len(d["rival"])), (5, 5))
        self.assertEqual(sum(1 for f in d["aliado"] if f["soy_yo"]), 1)
        self.assertIsNotNone(d["duelo"])
        self.assertIsNotNone(d["jungla"]["mapa"])
        self.assertEqual(d["jungla"]["mapa"]["inicial"], "3")
        self.assertTrue(d["plan"])
        self.assertEqual(d["hero"]["cabecera"], "Clasificatoria solo/dúo · Pantalla de carga")
        self.assertEqual(d["lineas"]["titulo"], "Dónde va a haber errores")

    def test_en_partida_nada_de_lo_que_riot_no_deja(self):
        e = self.estado("juego")
        d = vistas.partida(e)["datos"]
        self.assertEqual(d["plan"], [])
        self.assertIsNone(d["duelo"])
        self.assertIsNone(d["jungla"]["mapa"])
        self.assertEqual(d["lineas"]["titulo"], "Líneas")
        self.assertTrue(all(not l["veredicto"] for l in d["lineas"]["lineas"]))
        ov = vistas.overlay(e)
        self.assertIsNone(ov["duelo"])
        self.assertEqual(ov["destacado"]["plan"], [])
        self.assertEqual(ov["atajo"], "Suelta")

    def test_de_mid_tu_rival_de_linea_y_tu_rol(self):
        app = demo(self)
        self.assertEqual(app.elegir_rol("MIDDLE"), {"ok": True})
        e = app.estado()
        d = vistas.partida(e)["datos"]
        mia = next(f for f in d["aliado"] if f["soy_yo"])
        self.assertEqual((mia["rol"]["txt"], d["hero"]["rol"]), ("Mid", "Mid"))
        self.assertEqual(d["elegir_rol"]["actual"], "MIDDLE")
        self.assertEqual(d["elegir_rol"]["motivo"], "elegido por ti")
        self.assertEqual([o["txt"] for o in d["elegir_rol"]["opciones"]], ["Top", "Jungla", "Mid", "ADC", "Support"])
        rl = d["rival_linea"]
        self.assertEqual((rl["titulo"], rl["campeon"], rl["mapa"]), ("Tu rival de línea", "Qiyana", None))
        self.assertIn("14 partidas de mid", rl["nota"])
        self.assertEqual(len(rl["tarjetas"]), 6)
        self.assertIsNone(d["duelo"])  # el duelo de ejemplo es el de jungla
        self.assertTrue(d["plan"][0].startswith("Qiyana suele llegar al 10 con +410 de oro"))
        ov = vistas.overlay(e)
        self.assertEqual(ov["jungla"]["titulo"], "Tu rival de línea · Qiyana")
        self.assertEqual(ov["jungla"]["sub"], "14 partidas de mid · 6 líneas de tiempo")
        # Ya jugando, sus tarjetas van en neutro, como las del jungla (normas de Riot).
        app.elegir_escena("juego")
        d = vistas.partida(app.estado())["datos"]
        self.assertEqual({t["tono"] for t in d["rival_linea"]["tarjetas"]}, {"neutro"})
        self.assertEqual(d["plan"], [])
        self.assertEqual(app.elegir_rol("SUPPORT"), {"ok": False, "error": "Ese rol no existe."})

    def test_fuera_de_la_grieta_lo_basico(self):
        app = demo(self, panel=panel_aram())
        e = app.estado()
        d = vistas.partida(e)["datos"]
        self.assertTrue(d["basico"])
        self.assertIsNone(d["elegir_rol"])  # en ARAM no hay posiciones que elegir
        self.assertTrue(d["hero"]["sub"].startswith("En ARAM no hay posiciones"))
        self.assertEqual({(f["forma"], f["con_campeon"], f["cargando"]) for f in d["aliado"] + d["rival"]}, {(None, None, "")})
        ov = vistas.overlay(e)
        self.assertTrue(ov["basico"])
        self.assertIsNone(ov["jungla"])
        mia = next(f for f in ov["aliado"] if f["soy_yo"])
        self.assertEqual(mia["wr"], {"txt": "487k", "tono": "", "linea2": "maestría"})  # como en la tabla

    def test_en_un_modo_apagado_lo_dice(self):
        e = dict(self.estado("carga"), panel=None, apagada="ARAM")
        p = vistas.partida(e)
        self.assertEqual((p["vista"], p["datos"]["titulo"], p["datos"]["pasos"]), ("espera", "ARAM: sin panel", False))
        self.assertIn("Modos de juego", p["datos"]["texto"])

    def test_seleccion_fuera_de_la_grieta(self):
        s = vistas.seleccion({"basico": True, "modo": "ARAM", "mio": {"nombre": "Diana", "icono": ""}, "notas": []})
        self.assertEqual((s["pool"], s["duelo"], s["elegir_rol"]), (None, None, None))
        self.assertEqual(s["vs"]["vacio"], "En ARAM los rivales no se ven hasta la pantalla de carga.")

    def test_seleccion_de_campeon_tu_pool_contra_talon_y_lo_que_van_eligiendo(self):
        e = self.estado("seleccion")
        p = vistas.partida(e)
        self.assertEqual(p["vista"], "seleccion")
        s = p["datos"]
        self.assertEqual(s["pool"]["titulo"], "Tu pool contra Talon")
        self.assertEqual([f["nombre"] for f in s["pool"]["filas"]][:2], ["Viego", "Maestro Yi"])
        self.assertTrue(s["vs"]["filas"]["filas"])
        self.assertIn("36V 23D", s["hero"]["sub"])

    def test_overlay_antes_de_empezar(self):
        ov = vistas.overlay(self.estado("carga"))
        self.assertFalse(ov["esperando"])
        self.assertEqual(ov["titulo"], "Pantalla de carga")
        self.assertTrue(all(len(f["etiquetas"]) <= 2 for f in ov["aliado"] + ov["rival"]))
        self.assertIsNotNone(ov["duelo"])
        self.assertEqual(len(ov["duelo"]["datos"]), 2)
        self.assertTrue(ov["destacado"]["plan"])
        self.assertEqual(vistas.overlay({"panel": None}), {"esperando": True})

    def test_espera_y_lo_comun(self):
        e = self.estado("carga")
        c = vistas.comun(e)
        self.assertEqual(c["fase"], {"txt": "En partida", "tono": "vivo"})
        self.assertEqual(c["cuota"]["txt"], "0/96")
        self.assertIsNone(c["clave"])
        self.assertEqual(c["demo"], {"escena": "carga"})
        espera = vistas.partida(
            {
                "panel": None,
                "seleccion": None,
                "fase": None,
                "fase_txt": "Cliente del LoL cerrado",
                "overlay": {"activo": True, "atajo": "ctrl+tab"},
            }
        )
        self.assertEqual(espera["vista"], "espera")
        self.assertEqual(espera["datos"]["teclas"], ["CTRL", "TAB"])
        self.assertIn("Abre el cliente del LoL", espera["datos"]["texto"])

    def test_ningun_jugador_de_la_demo_es_de_verdad(self):
        p = leer("panel.json")
        for f in p["equipos"]["aliado"] + p["equipos"]["rival"]:
            self.assertEqual(f["tag"], "DEMO")


class Revisiones(unittest.TestCase):
    def test_lo_de_hoy_empieza_a_las_seis(self):
        ahora = datetime(2026, 11, 8, 2, 0)  # de madrugada: cuenta lo de ayer desde las 6:00
        lista = [
            {"fecha": datetime(2026, 11, 8, 1, 0).timestamp() * 1000, "gana": True, "lp": 20},
            {"fecha": datetime(2026, 11, 7, 22, 0).timestamp() * 1000, "gana": False, "lp": -18},
            {"fecha": datetime(2026, 11, 7, 5, 0).timestamp() * 1000, "gana": True, "lp": 21},
        ]
        hoy = vistas.hoy(lista, ahora)
        assert hoy is not None
        self.assertEqual((hoy["v"], hoy["d"]), (1, 1))
        self.assertEqual(hoy["lp"], {"txt": "+2 LP", "tono": "bien"})
        self.assertEqual(hoy["racha"], [False, True])  # de la más antigua a la última
        self.assertIsNone(vistas.hoy(lista[2:], ahora))
        sin_lp = vistas.hoy([{"fecha": ahora.timestamp() * 1000, "gana": True, "lp": None}], ahora)
        assert sin_lp is not None
        self.assertIsNone(sin_lp["lp"])

    def test_lista_tendencias_y_mapa_de_muertes(self):
        app = demo(self)
        r = vistas.revisiones(app.revisiones())
        self.assertEqual(r["resumen"], "1V 1D")
        self.assertEqual(r["lista"][0]["kda"], "4/8/6")
        self.assertEqual(
            [t["nombre"] for t in r["tendencias"]["tablas"]], ["Sesión", "Hora", "Duración", "Contra tu rival de posición"]
        )
        m = r["muertes"]
        self.assertEqual([b["id"] for b in m["botones"]], ["todas", "antes", "despues", "derrotas"])
        self.assertEqual(len(m["puntos"]["todas"]), m["n"])
        self.assertEqual(len(m["puntos"]["antes"]) + len(m["puntos"]["despues"]), m["n"])
        for p in m["puntos"]["todas"]:
            self.assertTrue(0 <= p["xy"][0] <= 1 and 0 <= p["xy"][1] <= 1)
            self.assertTrue(p["id"])

    def test_detalle_de_una_revision(self):
        app = demo(self)
        rid = app.revisiones()["lista"][0]["id"]
        r = app.revision(rid)
        assert r is not None
        d = vistas.detalle(r, r["dif_oro"])
        self.assertEqual((d["resultado"], d["campeon"], d["duracion"]), ("Derrota", "Diana", "29:53"))
        self.assertEqual(d["metricas"][0]["kda"], ["4", "8", "6"])
        self.assertEqual(d["grafico"]["final"]["txt"], "−11,4k")
        self.assertEqual(len(d["muertes"]), 8)
        self.assertTrue(d["muertes"][0]["clip"])
        self.assertEqual(d["comparacion"]["rival"], "Maestro Yi")
        self.assertEqual(d["comparacion"]["filas"][0]["oro"]["tono"], "mal")
        self.assertTrue(d["prevision"])
        self.assertTrue(d["ref_titulo"].startswith("Comparado con"))
        self.assertTrue(all(o["quien"] in ("tu equipo, contigo", "tu equipo, sin ti", "rival") for o in d["objetivos"]))
        self.assertIsNone(vistas.detalle(r, None)["grafico"])  # una revisión sin el oro: sin gráfico


class AjustesYDemo(unittest.TestCase):
    def test_formulario_con_lo_guardado(self):
        app = demo(self)
        a = vistas.ajustes(app.ajustes())
        self.assertTrue(a["overlay"])
        self.assertEqual(a["atajo"], "ctrl+tab")
        self.assertEqual(a["opacidad"], 94)
        self.assertIn("Driftmark#DEMO", a["cuentas"])
        self.assertEqual(a["referencias"][0]["campeon"], "Diana")
        self.assertIn("partidas suyas con ese campeón", a["referencias"][0]["estado"])
        self.assertIn("Diana", a["campeones"])
        self.assertTrue(a["version"].startswith("Deep Prep "))

    def test_tu_rol_y_los_modos_de_juego(self):
        a = vistas.ajustes(dict(leer("ajustes.json")["config"], rol="MIDDLE", modos={"aram": False}))
        self.assertEqual(a["rol"], "MIDDLE")
        self.assertEqual([r["id"] for r in a["roles"]], ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"])
        modos = {m["k"]: m["activo"] for m in a["modos"]}
        self.assertEqual(
            modos,
            {
                "clasificatoria": True,
                "flexible": True,
                "normales": True,
                "clash": True,
                "aram": False,
                "arena": False,
                "otros": False,
            },
        )
        self.assertEqual(vistas.ajustes({})["rol"], "JUNGLE")

    def test_leer_filas_por_id_del_campeon_sin_filas_incompletas(self):
        campeones = [{"id": 131, "nombre": "Diana"}, {"id": 91, "nombre": "Talon"}]
        filas = [("diana ", " nota "), ("Talon", ""), ("Nadie", "x"), ("TALON", "otra")]
        self.assertEqual(vistas.leer_filas(filas, campeones), {"131": "nota", "91": "otra"})

    def test_novedades_parrafos_y_puntos(self):
        n = vistas.novedades(
            {"version": "2.1.0", "notas": "# Interfaz nueva\nSin navegador.\n- Barra integrada\n* Gráfico de oro\n• Más rápida"}
        )
        assert n is not None
        self.assertEqual(n["parrafos"], ["Interfaz nueva", "Sin navegador."])
        self.assertEqual(n["puntos"], ["Barra integrada", "Gráfico de oro", "Más rápida"])
        self.assertIsNone(vistas.novedades(None))

    def test_escenas_de_la_demo(self):
        self.assertEqual([e["id"] for e in vistas.ESCENAS], ["seleccion", "carga", "juego", "revisiones", "ajustes"])
        self.assertEqual([e["id"] for e in vistas.ESCENAS if e["overlay"]], ["carga", "juego"])
        self.assertEqual(vistas.escena_actual({"escena": "juego"}, "partida"), "juego")
        self.assertEqual(vistas.escena_actual({"escena": "juego"}, "ajustes"), "ajustes")


class Interfaz(unittest.TestCase):
    def test_los_colores_de_tema_qml_son_los_de_vistas(self):
        tema = (QML / "Tema.qml").read_text(encoding="utf-8")
        for nombre, color in vistas.COLOR.items():
            self.assertIn(f'readonly property color {nombre}: "{color}"', tema, nombre)

    def test_cada_pieza_de_qml_esta_en_el_qmldir(self):
        qmldir = (QML / "qmldir").read_text(encoding="utf-8")
        for f in QML.glob("*.qml"):
            self.assertRegex(qmldir, rf"(?m)^(singleton )?{f.stem} 1\.0 {f.name}$")

    def test_ninguna_pieza_usa_lo_del_panel_web(self):
        for f in QML.glob("*.qml"):
            self.assertIsNone(re.search(r"https?://127\.0\.0\.1|/api/", f.read_text(encoding="utf-8")), f.name)


@unittest.skipUnless(HAY_QT, "sin PySide6")
class Barra(unittest.TestCase):
    def setUp(self):
        from deepprep.nativa import marco

        self.m = marco

    def zona(self, x, y, maximizada=False, sobre_max=False, sobre_app=False):
        return self.m.zona(x, y, 1500, 950, 56, maximizada, sobre_max, sobre_app)

    def test_bordes_y_esquinas_cambian_el_tamano(self):
        m = self.m
        self.assertEqual(self.zona(2, 400), m.HTLEFT)
        self.assertEqual(self.zona(1498, 400), m.HTRIGHT)
        self.assertEqual(self.zona(700, 2), m.HTTOP)
        self.assertEqual(self.zona(700, 948), m.HTBOTTOM)
        self.assertEqual(self.zona(1, 1), m.HTTOPLEFT)
        self.assertEqual(self.zona(1499, 1), m.HTTOPRIGHT)
        self.assertEqual(self.zona(1, 949), m.HTBOTTOMLEFT)
        self.assertEqual(self.zona(1499, 949), m.HTBOTTOMRIGHT)

    def test_la_barra_arrastra_salvo_lo_interactivo(self):
        m = self.m
        self.assertEqual(self.zona(700, 28), m.HTCAPTION)
        self.assertEqual(self.zona(700, 28, sobre_app=True), m.HTCLIENT)
        self.assertEqual(self.zona(1431, 28, sobre_max=True), m.HTMAXBUTTON)
        self.assertEqual(self.zona(700, 300), m.HTCLIENT)  # debajo de la barra, todo es de la app

    def test_maximizada_no_hay_bordes(self):
        m = self.m
        self.assertEqual(self.zona(700, 1, maximizada=True), m.HTCAPTION)
        self.assertEqual(self.zona(1, 400, maximizada=True), m.HTCLIENT)


@unittest.skipUnless(HAY_QT, "sin PySide6")
class PuenteConLaApp(unittest.TestCase):
    def setUp(self):
        from deepprep.nativa import puente

        self.app = demo(self)
        self.p = puente.Puente(self.app, lambda r: r.get("dif_oro"))

    def test_solo_se_puede_pedir_lo_de_la_lista(self):
        self.assertEqual(
            sorted(self.p.acciones()),
            [
                "actualizar",
                "ajustes",
                "buscar",
                "carpeta",
                "clave",
                "clip",
                "escena",
                "guardarAjustes",
                "novedadesVistas",
                "revision",
                "revisiones",
                "rol",
                "salir",
                "volver",
            ],
        )

    def test_en_la_demo_no_se_actualiza(self):
        self.assertEqual(self.p.acciones()["actualizar"](), {"ok": False, "error": "En la demo no se instala nada."})

    def test_las_vistas_del_estado(self):
        v = self.p.vistas_de(self.app.estado())
        self.assertEqual(v["modo"], "carga")
        self.assertEqual(v["partida"]["vista"], "panel")
        self.assertEqual(v["inicio"], 0.0)  # en la carga no hay reloj
        self.app.elegir_escena("juego")
        v = self.p.vistas_de(self.app.estado())
        self.assertGreater(v["inicio"], 0)

    def test_una_revision_con_su_grafico(self):
        rid = self.app.revisiones()["lista"][0]["id"]
        r = self.p.acciones()["revision"](rid)
        self.assertEqual(r["grafico"]["final"]["txt"], "−11,4k")
        self.assertIsNone(self.p.acciones()["revision"]("no-existe"))

    def test_guardar_ajustes_del_formulario(self):
        a = self.p.acciones()["ajustes"]()
        form = {
            "overlay": False,
            "atajo": "alt+x",
            "opacidad": 80,
            "siempre": True,
            "grabar": False,
            "codificador": "cpu",
            "max_gb": "10",
            "cuentas": "Driftmark#DEMO\n\n Halcyon#DEMO ",
            "reglas": "Una regla",
            "comparar_con": a["comparar_con"],
            "perfil": "",
            "referencias": [{"campeon": "diana", "texto": "Larkspur#DEMO"}],
            "notas": [{"campeon": "Talon", "texto": "Cuidado al 6"}, {"campeon": "Nadie", "texto": "x"}],
        }
        r = self.p.acciones()["guardarAjustes"](form)
        self.assertTrue(r["ok"], r)
        cfg = self.app.cfg
        self.assertEqual((cfg["overlay"], cfg["atajo_overlay"], cfg["overlay_opacidad"]), (False, "alt+x", 0.8))
        self.assertEqual(cfg["cuentas"], ["Driftmark#DEMO", "Halcyon#DEMO"])
        self.assertEqual(cfg["recordatorios"], ["Una regla"])
        self.assertEqual(list(cfg["notas"].values()), ["Cuidado al 6"])
        self.assertEqual(r["ajustes"]["atajo"], "alt+x")  # vuelve con los ajustes ya guardados


@unittest.skipUnless(HAY_QT, "sin PySide6")
class VentanasConQt(unittest.TestCase):
    """La interfaz de verdad, sin pantalla (Qt en «offscreen»): que todo el QML cargue y funcione sin un solo aviso, y
    lo que hacen las ventanas al cerrar, enseñar y salir."""

    qapp: object = None

    @staticmethod
    def parar(v) -> None:
        v.desmontar()  # la ventana y su QML, fuera ya (si no, avisarían en mitad de otra prueba al recoger la basura)

    @classmethod
    def setUpClass(cls):
        import os

        from PySide6.QtGui import QGuiApplication

        if QGuiApplication.instance() is None:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
            cls.qapp = QGuiApplication([])
        # Las cachés de Qt, fuera de la carpeta de datos (desde el código, la del proyecto).
        cache = tempfile.TemporaryDirectory(prefix="deepprep-qt-", ignore_cleanup_errors=True)
        cls.addClassCleanup(cache.cleanup)
        os.environ["QML_DISK_CACHE_PATH"] = str(Path(cache.name) / "qmlcache")
        parche = mock.patch("deepprep.nativa.ventanas.CACHE_QT", Path(cache.name))
        parche.start()
        cls.addClassCleanup(parche.stop)

    def setUp(self):
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler

        from deepprep.nativa.ventanas import VentanasQt

        self.avisos: list[str] = []

        def recoger(tipo, contexto, texto):
            # Sin pantalla, Qt no encuentra fuentes del sistema y lo dice una vez (la app usa las de Windows).
            if tipo != QtMsgType.QtDebugMsg and not texto.startswith("QFontDatabase: Cannot find font directory"):
                self.avisos.append(texto)

        qInstallMessageHandler(recoger)
        self.addCleanup(qInstallMessageHandler, None)
        # Sin red: las imágenes de Data Dragon no llegan (ni se guardan en la carpeta de datos de las pruebas).
        sin_red = mock.patch("deepprep.ddragon.imagen", return_value=None)
        sin_red.start()
        self.addCleanup(sin_red.stop)
        self.app = demo(self)
        self.v = VentanasQt(self.app, titulo="Deep Prep · prueba")
        self.addCleanup(self.parar, self.v)

    def esperar(self, ms: int = 600):
        from PySide6.QtTest import QTest

        QTest.qWait(ms)

    def test_de_mid_y_en_aram_sin_avisos(self):
        from deepprep.nativa.ventanas import VentanasQt

        principal = self.v.preparar()
        assert self.v.puente is not None
        # Como lo pide el selector de la interfaz: por el puente, que vuelve a leer el estado en seguida.
        self.assertEqual(self.v.puente.acciones()["rol"]("MIDDLE"), {"ok": True})
        self.esperar()
        partida = self.v.puente.property("partida")  # lo mismo que lee el QML
        self.assertEqual(partida["datos"]["rival_linea"]["campeon"], "Qiyana")
        aram = VentanasQt(demo(self, panel=panel_aram()), titulo="Deep Prep · ARAM")
        self.addCleanup(self.parar, aram)
        aram.preparar().setProperty("vista", "partida")
        self.esperar(1300)
        principal.setProperty("vista", "ajustes")
        self.esperar()
        self.assertEqual(self.avisos, [])

    def test_todo_el_qml_carga_sin_avisos(self):
        principal = self.v.preparar()
        self.assertEqual(principal.title(), "Deep Prep · prueba")
        self.assertIsNotNone(self.v.flotante)  # el overlay, con la configuración de la demo
        for vista in ("partida", "revisiones", "ajustes"):  # cada pestaña pide sus datos al abrirse
            principal.setProperty("vista", vista)
            self.esperar()
        for escena in ("seleccion", "juego", "carga"):
            self.app.elegir_escena(escena)
            principal.setProperty("vista", "partida")
            self.esperar(1300)
        self.assertEqual(self.avisos, [])

    def test_cerrar_solo_esconde_y_el_acceso_directo_la_vuelve_a_ensenar(self):
        self.v.preparar()
        self.assertFalse(self.v.cerrar())
        self.assertIsNotNone(self.v.oculta_desde)
        self.v.mostrar_principal()
        self.assertIsNone(self.v.oculta_desde)
        self.v.saliendo = True
        self.assertTrue(self.v.cerrar())

    def test_en_la_demo_cerrar_es_salir(self):
        from deepprep.nativa.ventanas import VentanasQt

        v = VentanasQt(self.app, demo=True)
        self.addCleanup(self.parar, v)
        v.preparar()
        self.assertTrue(v.cerrar())
        self.assertTrue(v.saliendo)

    def test_la_ventana_del_overlay(self):
        from deepprep.nativa.ventanas import ALTO_OVERLAY, ANCHO_OVERLAY, VentanaQt

        self.v.preparar()
        flotante = self.v.flotante
        assert flotante is not None
        w = VentanaQt(flotante, ANCHO_OVERLAY, ALTO_OVERLAY, 0.5)
        w.mostrar()
        self.esperar(100)
        self.assertTrue(flotante.isVisible())
        self.assertAlmostEqual(flotante.opacity(), 0.5, places=2)
        self.assertEqual((flotante.width(), flotante.height()), (ANCHO_OVERLAY, ALTO_OVERLAY))
        w.opacidad(0.0)  # nunca del todo invisible: como mínimo, la de overlay.VentanaWin32
        w.ocultar()
        self.esperar(100)
        self.assertFalse(flotante.isVisible())
        self.assertAlmostEqual(flotante.opacity(), 60 / 255, places=2)

    def test_copiar_el_nombre_al_portapapeles(self):
        from PySide6.QtGui import QGuiApplication

        self.v.preparar()
        assert self.v.puente is not None
        self.v.puente.copiar("Driftmark#DEMO")
        self.assertEqual(QGuiApplication.clipboard().text(), "Driftmark#DEMO")

    def test_los_avisos_de_qt_van_al_registro(self):
        from PySide6.QtCore import QMessageLogContext, QtMsgType

        from deepprep.nativa.ventanas import al_registro

        with self.assertLogs("deepprep.nativa.ventanas", "WARNING") as registro:
            al_registro(QtMsgType.QtWarningMsg, QMessageLogContext(), "Falta algo")
            al_registro(QtMsgType.QtCriticalMsg, QMessageLogContext(), "Se rompió algo")
            al_registro(QtMsgType.QtDebugMsg, QMessageLogContext(), "nada")
        self.assertEqual(
            registro.output,
            ["WARNING:deepprep.nativa.ventanas:Qt: Falta algo", "ERROR:deepprep.nativa.ventanas:Qt: Se rompió algo"],
        )

    def test_la_respuesta_llega_a_la_funcion_de_qml(self):
        from PySide6.QtQml import QJSValue

        self.v.preparar()
        motor = self.v.motor
        assert motor is not None and self.v.puente is not None
        motor.globalObject().setProperty("recibido", QJSValue(""))
        cb: QJSValue = motor.evaluate("(function (r) { recibido = r.resumen; })")  # type: ignore[assignment]
        self.v.puente.llamar("revisiones", [], cb)
        self.esperar(800)
        self.assertEqual(motor.globalObject().property("recibido").toString(), "1V 1D")
        self.v.puente.llamar("noExiste", [], cb)  # lo que no está en la lista no se hace (y no rompe nada)


class DemoSinTusDatos(unittest.TestCase):
    def test_la_demo_no_es_tu_carpeta(self):
        # Las pruebas de la interfaz usan AppDemo con carpetas temporales, nunca la de tus datos.
        self.assertNotEqual(demo(self).carpeta, config.DATOS)
        self.assertEqual(copy.deepcopy(leer("panel.json"))["cola"], "Clasificatoria solo/dúo")


if __name__ == "__main__":
    unittest.main()
