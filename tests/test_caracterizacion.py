"""Pruebas de caracterización: fijan lo que sale hoy de las funciones grandes con los datos anonimizados de
tests/datos y de herramientas/maquetas, para poder reordenar el código sin cambiar nada de lo que se enseña.

Lo esperado está en tests/datos/esperado/*.json y salió del propio código. Se compara el JSON entero, también el
orden de las claves. Si un cambio en la salida es a propósito, se regenera y se revisa el diff:

    DEEPPREP_REGENERAR=1 py -X utf8 -m unittest tests.test_caracterizacion
"""

import copy
import datetime
import gzip
import json
import os
import types
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from deepprep import analisis as an
from deepprep import config
from deepprep import duelos as du
from deepprep import revision as rv
from deepprep.app import App
from deepprep.recolector import BaseDuelos
from tests.test_app import DatosFalsos, GrabadorFalso, LolFalso, RiotFalso, crear, esperar, montar

DATOS = Path(__file__).parent / "datos"
ESPERADO = DATOS / "esperado"
MAQUETA = Path(__file__).resolve().parent.parent / "herramientas" / "maquetas" / "partida.json"
REGENERAR = os.environ.get("DEEPPREP_REGENERAR") == "1"
DIA_MS = 86_400_000
# Objetos que cuentan como primer objeto completo (en la app salen de Data Dragon).
LEGENDARIOS = {3031, 3036, 3046, 3071, 3074, 3078, 3085, 3087, 3091, 3094, 3100, 3124, 3135, 3147, 3157, 3181}
LEGENDARIOS |= {4630, 4633, 4645, 6333, 6655, 6670, 6672, 6697}


def cargar(nombre):
    with gzip.open(DATOS / nombre, "rt", encoding="utf-8") as f:
        return json.load(f)


CRUDO = cargar("partida.json.gz")
CRUDO_LINEA = cargar("linea.json.gz")
PARTIDA = an.reducir_partida(CRUDO)
LINEA = an.reducir_linea(CRUDO_LINEA)
LINEA_COMPLETA = rv.reducir_linea_completa(CRUDO_LINEA)
# Momento fijo para lo que depende de la hora (días desde una partida, etiquetas de maestría...): 3 días después.
AHORA_MS = PARTIDA["creacion"] + 3 * DIA_MS


def nombre(c):
    return f"Campeón {c}"


class Golden(unittest.TestCase):
    def comprobar(self, nombre_archivo, salida):
        texto = json.dumps(salida, ensure_ascii=False, indent=1) + "\n"
        ruta = ESPERADO / f"{nombre_archivo}.json"
        if REGENERAR:
            ruta.parent.mkdir(exist_ok=True)
            ruta.write_text(texto, encoding="utf-8", newline="\n")
            return
        esperado = ruta.read_text(encoding="utf-8")
        self.maxDiff = None
        self.assertEqual(json.loads(texto), json.loads(esperado))
        self.assertEqual(texto, esperado, "mismo contenido, pero cambia el orden de las claves")


def copias(partida, linea, n):
    """n copias de la partida (y su línea), cada una con otro id y un día más vieja."""
    partidas, lineas = [], {}
    for k in range(n):
        id_ = f"{partida['id']}_{k}"
        partidas.append(dict(partida, id=id_, creacion=partida["creacion"] - k * DIA_MS))
        lineas[id_] = dict(linea, id=id_)
    return partidas, lineas


# --- funciones puras -----------------------------------------------------------------------------------
class FuncionesPuras(Golden):
    def test_perfil_jungla(self):
        partidas, lineas = copias(PARTIDA, LINEA, 5)
        # Un remake y una partida de otro mapa no cuentan.
        partidas += [dict(PARTIDA, id="remake", remake=True), dict(PARTIDA, id="aram", cola=450)]
        out = {}
        for j in (j for j in PARTIDA["jug"] if j["pos"] == "JUNGLE"):
            for equipo in (100, 200):
                out[f"{j['puuid']}_{equipo}"] = an.perfil_jungla(j["puuid"], partidas, lineas, j["campeon"], equipo)
            out[f"{j['puuid']}_una"] = an.perfil_jungla(j["puuid"], [PARTIDA], {PARTIDA["id"]: LINEA}, j["campeon"], 100)
            out[f"{j['puuid']}_sin_lineas"] = an.perfil_jungla(j["puuid"], partidas, {}, 1, 200)
            out[f"{j['puuid']}_otro_campeon"] = an.perfil_jungla(j["puuid"], partidas, lineas, 1, j["equipo"])
        self.comprobar("perfil_jungla", out)

    def test_mi_historial(self):
        partidas, _ = copias(PARTIDA, LINEA, 4)
        out = {}
        for yo in PARTIDA["jug"]:
            rivales = [
                {"campeon": j["campeon"], "pos": j["pos"], "nombre_campeon": nombre(j["campeon"])}
                for j in PARTIDA["jug"]
                if j["equipo"] != yo["equipo"]
            ]
            rivales.append({"campeon": 1, "pos": "", "nombre_campeon": nombre(1)})  # sin cruces
            presentes = {j["puuid"]: j["nombre"] for j in PARTIDA["jug"] if j["puuid"] != yo["puuid"]}
            out[yo["puuid"]] = an.mi_historial({yo["puuid"]}, partidas, yo["campeon"], rivales, presentes, AHORA_MS, yo["pos"])
            out[f"{yo['puuid']}_otro_campeon"] = an.mi_historial({yo["puuid"]}, partidas, 1, rivales, {}, AHORA_MS)
        self.comprobar("mi_historial", out)

    def test_extraer(self):
        self.comprobar("extraer", du.extraer(CRUDO, CRUDO_LINEA, LEGENDARIOS))

    def test_analizar(self):
        base = BaseDuelos(":memory:")
        registros = du.extraer(CRUDO, CRUDO_LINEA, LEGENDARIOS)
        # Para cada duelo, el registro de cada lado visto como si fuera de a contra b: la mitad gana y la otra pierde.
        for r in registros:
            otro = next(x for x in registros if x["pos"] == r["pos"] and x["a"] == r["b"])
            for k in range(8):
                base.guardar(f"A_{r['pos']}_{r['a']}_{k}", [dict(r, puuid=f"p{k}")])
                base.guardar(f"B_{r['pos']}_{r['a']}_{k}", [dict(otro, a=r["a"], b=r["b"], puuid=f"q{k}")])
        out = {}
        for r in registros:
            duelo = base.duelo(r["a"], r["pos"], r["b"])
            clave = f"{r['pos']}_{r['a']}_{r['b']}"
            res = du.analizar(duelo, [], nombre(r["a"]), nombre(r["b"]), r["pos"], lambda i: f"Objeto {i}", lambda i: f"Runa {i}")
            res["tu"] = du.comparar([r], [x for x in duelo if x["g"]], r["pos"], "Ganan este duelo", minimo=3)
            out[clave] = res
            out[f"{clave}_poco"] = du.analizar(duelo[:11], [], "A", "B", r["pos"])
        self.comprobar("analizar", out)

    def test_revisar(self):
        panel = json.loads(MAQUETA.read_text(encoding="utf-8"))["panel"]
        out = {}
        for j in PARTIDA["jug"]:
            out[j["puuid"]] = rv.revisar(PARTIDA, LINEA_COMPLETA, j["puuid"], nombre, panel, {1: 20, 2: -900})
        diana = next(j for j in PARTIDA["jug"] if j["campeon"] == 131)
        out["sin_panel_ni_video"] = rv.revisar(PARTIDA, LINEA_COMPLETA, diana["puuid"], nombre)
        out["con_un_desfase"] = rv.revisar(PARTIDA, LINEA_COMPLETA, diana["puuid"], nombre, {"gank": None}, 35)
        out["nadie"] = rv.revisar(PARTIDA, LINEA_COMPLETA, "nadie", nombre)
        out["mapa_muertes"] = rv.mapa_muertes(out[j["puuid"]] for j in PARTIDA["jug"])
        self.comprobar("revisar", out)

    def test_tendencias(self):
        partidas, _ = copias(PARTIDA, LINEA, 6)
        # Unas seguidas (misma sesión) y otras con días por medio, con distintas duraciones.
        for k, m in enumerate(partidas):
            m["creacion"] = PARTIDA["creacion"] - k * (2_400_000 if k < 3 else DIA_MS)
            m["duracion"] = (1200, 1793, 2400)[k % 3]

        def hora(ms):
            return datetime.datetime.fromtimestamp(ms / 1000, datetime.UTC).hour

        out = {j["puuid"]: rv.tendencias(partidas, {j["puuid"]}, nombre, hora) for j in PARTIDA["jug"]}
        self.comprobar("tendencias", out)

    def test_para_el_modo(self):
        # Con el juego empezado solo datos: sin plan, sin veredictos, sin colores de alerta ni mapa del jungla.
        panel = json.loads(MAQUETA.read_text(encoding="utf-8"))["panel"]
        app: Any = types.SimpleNamespace  # solo hace falta el modo
        out = {modo: App._para_el_modo(app(modo=modo), copy.deepcopy(panel)) for modo in ("carga", "juego")}
        self.comprobar("para_el_modo", out)


# --- la app entera, con el cliente del LoL y la API de Riot de mentira ------------------------------------------
# Cada jugador de la partida en vivo (tests/datos/activa.json) ocupa el sitio de uno de la partida de tests/datos,
# del mismo equipo y con el smite en la jungla: {índice en vivo: índice en la partida guardada}.
SITIO = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 7, 7: 6, 8: 8, 9: 9}


def con_jugadores(juego, indices, id_, dias_antes=0):
    """La partida guardada (y su línea) con los jugadores en vivo de esos índices en su sitio, con su campeón."""
    m, l = copy.deepcopy(CRUDO), copy.deepcopy(CRUDO_LINEA)
    m["metadata"]["matchId"] = l["metadata"]["matchId"] = id_
    m["info"]["gameCreation"] -= dias_antes * DIA_MS
    for i in indices:
        vivo = juego["participants"][i]
        p = m["info"]["participants"][SITIO[i]]
        for q in l["info"]["participants"]:
            if q["puuid"] == p["puuid"]:
                q["puuid"] = vivo["puuid"]
        m["metadata"]["participants"] = [vivo["puuid"] if x == p["puuid"] else x for x in m["metadata"]["participants"]]
        p["puuid"], p["championId"] = vivo["puuid"], vivo["championId"]
    return m, l


class RiotConHistorial(RiotFalso):
    """Cada jugador tiene en su historial las partidas guardadas en las que sale."""

    def __init__(self, juego, partidas):
        super().__init__(juego)
        self.partidas = partidas  # {id: (partida, línea)}
        self.jugadas = 0  # partidas de más en la liga (tras acabar la de hoy)

    def ligas(self, puuid, cancelada=None):
        ligas = super().ligas(puuid)
        ligas[0] = dict(ligas[0], wins=72 + self.jugadas, leaguePoints=18 + 21 * self.jugadas)
        return ligas

    def ids_partidas(self, puuid, **kw):
        return [i for i, (m, _) in self.partidas.items() if puuid in m["metadata"]["participants"]]

    def partida(self, id_, **kw):
        self.pedida = id_
        return copy.deepcopy(self.partidas[id_][0]) if id_ in self.partidas else self.crudo

    def linea(self, id_, **kw):
        return copy.deepcopy(self.partidas[id_][1]) if id_ in self.partidas else self.crudo_linea


def sin_lo_variable(estado):
    """Fuera la versión de la app (cambia al publicar) y las novedades (dependen de la carpeta de datos)."""
    return {k: v for k, v in estado.items() if k not in ("version", "novedades")}


def instantanea(x):
    """Copia de lo que sale en este momento (el panel de la sesión se sigue retocando después)."""
    return json.loads(json.dumps(x))


def con_la_hora_fija(fn, *args, **kw):
    with mock.patch("time.time", return_value=AHORA_MS / 1000):
        return fn(*args, **kw)


class AppEntera(Golden):
    salidas: dict[str, Any]

    @classmethod
    def setUpClass(cls):
        juego = json.loads((DATOS / "activa.json").read_text(encoding="utf-8"))
        juego["participants"][0]["puuid"] = "puuid-yo"
        partidas = {
            "EUW1_7000000001": con_jugadores(juego, range(10), "EUW1_7000000001"),
            # Otra partida de hace un día con tres de tu equipo y dos rivales: vienen juntos (premades).
            "EUW1_7000000000": con_jugadores(juego, (0, 1, 2, 6, 7), "EUW1_7000000000", dias_antes=1),
        }
        cfg = dict(
            config.POR_DEFECTO,
            cuentas=["Yo#EUW"],
            revisar=False,
            recordatorios=["Mirar el minimapa"],
            notas={"421": "Pega fuerte a nivel 3", "40": "Guardar la E"},
        )
        riot = RiotConHistorial(juego, partidas)
        lol: Any = LolFalso()
        datos = DatosFalsos()
        datos.roles = {421: {"TOP": 1.0}, 887: {"JUNGLE": 1.0}}
        app = crear(cfg, riot, lol, datos=datos, grabador=GrabadorFalso())
        app.comprobar_clave()
        # Duelos de Master+ de tu campeón (40) contra cada rival, en cualquier posición, y tres partidas tuyas.
        registros = du.extraer(CRUDO, CRUDO_LINEA, LEGENDARIOS)
        mios = {r["pos"]: r for r in reversed(registros)}  # el primero de cada posición
        for b in (p["championId"] for p in juego["participants"][5:]):
            for r in registros:
                otro = next(x for x in registros if x["pos"] == r["pos"] and x["a"] == r["b"])
                for k in range(8):
                    app.duelos.guardar(f"A_{r['pos']}_{b}_{r['a']}_{k}", [dict(r, a=40, b=b, puuid=f"p{k}")])
                    app.duelos.guardar(f"B_{r['pos']}_{b}_{r['a']}_{k}", [dict(otro, a=40, b=b, puuid=f"q{k}")])
            for pos, r in mios.items():
                for k in range(3):
                    app.duelos.guardar(f"YO_{pos}_{b}_{k}", [dict(r, a=40, b=b, puuid="puuid-yo")])
        cls.salidas = {}

        lol.fase = "InProgress"
        app.vigia.paso()
        assert esperar(app.sesion)
        cls.salidas["carga"] = instantanea(sin_lo_variable(con_la_hora_fija(app.estado)))
        lol.segundos = 90.0
        app.actualizar_modo()
        cls.salidas["juego"] = instantanea(sin_lo_variable(con_la_hora_fija(app.estado)))

        lol.fase, lol.segundos = "EndOfGame", None
        app.vigia.paso()
        lol.fase = "ChampSelect"
        lol.eleccion = {"mio": 40, "aliados": [59], "rivales": [887, 421], "cola": 420, "pos": "TOP"}
        con_la_hora_fija(app.vigia.paso)
        cls.salidas["seleccion"] = instantanea(sin_lo_variable(con_la_hora_fija(app.estado)))

        # La revisión de la partida de hoy, ya publicada (con una partida más en la liga: LP ganados).
        riot.jugadas = 1
        panel = cls.salidas["carga"]["panel"]
        cls.salidas["revision"] = instantanea(app.revisor.revisar(7000000001, "puuid-yo", panel, None, intentos=1, pausa=0))
        revisiones = app.revisiones()
        # Las franjas horarias van con la hora local del PC (cambia de una máquina a otra): ya están en tendencias.json.
        revisiones["tendencias"] = {k: v for k, v in revisiones["tendencias"].items() if k != "franjas"}
        cls.salidas["revisiones"] = instantanea(revisiones)
        cls.salidas["una_revision"] = instantanea(app.revision("EUW1_7000000001"))
        cls.salidas["ajustes"] = instantanea(sin_lo_variable(app.ajustes()))

        # Lo que montan las pruebas de tests/test_app.py, tal cual.
        app2, _, lol2 = montar()
        lol2.fase = "InProgress"
        app2.vigia.paso()
        assert esperar(app2.sesion)
        cls.salidas["montar"] = instantanea(sin_lo_variable(con_la_hora_fija(app2.estado)))

    def test_panel_en_la_pantalla_de_carga(self):
        self.comprobar("app_carga", self.salidas["carga"])

    def test_panel_con_el_juego_empezado(self):
        self.comprobar("app_juego", self.salidas["juego"])

    def test_seleccion_de_campeon(self):
        self.comprobar("app_seleccion", self.salidas["seleccion"])

    def test_revision(self):
        self.comprobar(
            "app_revision",
            {k: self.salidas[k] for k in ("revision", "revisiones", "una_revision", "ajustes")},
        )

    def test_estado_de_las_pruebas_de_la_app(self):
        self.comprobar("app_montar", self.salidas["montar"])


if __name__ == "__main__":
    unittest.main()
