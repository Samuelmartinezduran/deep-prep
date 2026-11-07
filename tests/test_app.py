"""Pruebas del núcleo con un cliente del LoL y una API de Riot de mentira."""

import json
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest import mock

from deepprep import config, servidor
from deepprep import recolector as rec
from deepprep.app import App
from deepprep.base_duelos import BaseDuelos
from deepprep.cache import Cache
from deepprep.riot import ClaveInvalida, Limitador

DATOS = Path(__file__).parent / "datos"


class DatosFalsos:
    version = "0"
    roles: dict[int, dict[str, float]] = {}
    campeones = {131: {"nombre": "Diana", "clave": "Diana"}, 11: {"nombre": "Maestro Yi", "clave": "MasterYi"}}

    def nombre(self, id_):
        return f"Campeón {id_}"

    def icono(self, id_):
        return ""

    def splash(self, id_):
        return ""

    legendarios: set[int] = set()

    def objeto(self, id_):
        return f"Objeto {id_}"

    def runa(self, id_):
        return f"Runa {id_}"


class RiotFalso:
    region = "europe.api.riotgames.com"
    plataforma = "euw1.api.riotgames.com"  # como el cliente de verdad

    def __init__(self, juego):
        self.juego = juego
        self.limitador = Limitador()
        self.clave_mala = False

    def cuenta_por_riot_id(self, nombre, tag):
        if self.clave_mala:
            raise ClaveInvalida("caducada")
        return {"puuid": f"puuid-{nombre.lower()}", "gameName": nombre, "tagLine": tag}

    def partida_activa(self, puuid):
        if self.juego and any(p["puuid"] == puuid for p in self.juego["participants"]):
            return self.juego
        return None

    def ligas(self, puuid, cancelada=None):
        return [
            {"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "IV", "leaguePoints": 18, "wins": 72, "losses": 65},
            {"queueType": "RANKED_FLEX_SR", "tier": "PLATINUM", "rank": "II", "leaguePoints": 50, "wins": 10, "losses": 8},
        ]

    def maestrias(self, puuid, cancelada=None):
        return [{"championId": 1, "championPoints": 900000, "lastPlayTime": 0}]

    def ids_partidas(self, puuid, **kw):
        return []

    crudo = None  # partida y línea de tiempo que Riot "publica" al acabar (para la revisión)
    crudo_linea = None

    def partida(self, id_, **kw):
        self.pedida = id_
        return self.crudo

    def linea(self, id_, **kw):
        return self.crudo_linea


class GrabadorFalso:
    armados = 0

    def carpeta_reciente(self):
        return None

    def armar(self):
        self.armados += 1

    def estado(self):
        return {"carpeta": "", "parada": False} if self.armados else None


class LolFalso:
    ruta = Path("C:/no-existe")
    region: str | None = None  # plataforma que dice el cliente (None = no responde)
    fase: str | None = None

    def plataforma(self):
        return self.region

    eleccion: dict[str, Any] | None = None
    mapa_id = 11
    segundos: float | None = None  # reloj del juego: None en la pantalla de carga

    def reloj(self):
        return self.segundos

    def mapa(self):
        return self.mapa_id

    nombre = "Yo"

    def estado(self):
        return None if self.fase is None else {"fase": self.fase, "nombre": self.nombre, "tag": "EUW"}

    def seleccion(self):
        return self.eleccion


def crear(cfg, cliente, cliente_lol, **piezas):
    """La app con piezas de mentira: configuración en memoria (no escribe config.json) y bases en memoria."""
    piezas = {"cache": Cache(":memory:"), "datos": DatosFalsos(), "duelos": BaseDuelos(":memory:"), **piezas}
    return App(config.Configuracion.en_memoria(cfg), cliente=cliente, cliente_lol=cliente_lol, **piezas)


def montar(**piezas):
    juego = json.loads((DATOS / "activa.json").read_text(encoding="utf-8"))
    juego["participants"][0]["puuid"] = "puuid-yo"
    juego["participants"][5]["puuid"] = "puuid-otro"
    cfg = dict(config.POR_DEFECTO, cuentas=["Yo#EUW"], revisar=False)
    riot, lol = RiotFalso(juego), LolFalso()
    app = crear(cfg, riot, lol, **{"grabador": GrabadorFalso(), **piezas})
    app.comprobar_clave()
    return app, riot, lol


def esperar(sesion):
    limite = time.time() + 5
    while sesion.hechas < sesion.total and time.time() < limite:
        time.sleep(0.02)
    return sesion.hechas == sesion.total


class Deteccion(unittest.TestCase):
    def test_partida_propia_de_principio_a_fin(self):
        app, _, lol = montar()
        lol.fase = "Lobby"
        app.vigia.paso()
        self.assertIsNone(app.sesion)
        self.assertEqual(app.estado()["cuenta"], "Yo#EUW")

        lol.fase = "InProgress"
        app.vigia.paso()
        s = app.sesion
        self.assertEqual((s.origen, s.yo, s.mi_equipo), ("propia", "puuid-yo", 100))
        self.assertTrue(esperar(s))

        estado = app.estado()
        json.dumps(estado)  # el panel entero tiene que poder viajar como JSON
        p = estado["panel"]
        self.assertEqual((len(p["equipos"]["aliado"]), len(p["equipos"]["rival"])), (5, 5))
        self.assertEqual(sum(f["soy_yo"] for f in p["equipos"]["aliado"]), 1)
        self.assertEqual([f["rol"] for f in p["equipos"]["rival"]].count("JUNGLE"), 1)
        liga = p["equipos"]["aliado"][0]["liga"]
        self.assertEqual((liga["solo"]["txt"], liga["solo"]["lp"], liga["flex"]), ("Diamante IV", 18, None))
        self.assertEqual(p["recordatorios"], config.POR_DEFECTO["recordatorios"])
        self.assertFalse(p["terminada"])

        lol.fase = "EndOfGame"
        app.vigia.paso()
        self.assertTrue(app.sesion.terminada)
        self.assertIs(app.sesion, s)  # el panel se queda a la vista hasta la siguiente partida

    def test_misma_partida_no_se_reabre(self):
        app, _, lol = montar()
        lol.fase = "InProgress"
        app.vigia.paso()
        s = app.sesion
        app.vigia.ultimo_sondeo = 0
        app.vigia.paso()
        self.assertIs(app.sesion, s)

    def test_sin_cliente_pregunta_a_riot(self):
        app, _, _ = montar()
        app.vigia.paso()
        self.assertEqual(app.sesion.origen, "propia")

    def test_el_historial_se_pausa_con_la_partida_cerca(self):
        app, riot, lol = montar()
        lol.fase = "ChampSelect"
        app.vigia.paso()
        self.assertEqual(riot.limitador.tope_fondo, 0)
        lol.fase = "InProgress"
        app.vigia.paso()
        self.assertEqual(riot.limitador.tope_fondo, 85)


class Modo(unittest.TestCase):
    def test_previa_carga_y_juego(self):
        app, _, lol = montar()
        lol.fase = "ChampSelect"
        app.vigia.paso()
        self.assertEqual(app.estado()["modo"], "previa")
        lol.fase = "InProgress"
        app.vigia.paso()
        self.assertEqual((app.modo, app.reloj), ("carga", None))
        lol.segundos = 42.5
        app.actualizar_modo()
        self.assertEqual((app.estado()["modo"], app.estado()["reloj"]), ("juego", 42.5))
        lol.fase = "EndOfGame"
        app.vigia.paso()
        self.assertEqual(app.modo, "previa")

    def test_en_la_pantalla_de_carga_el_reloj_contesta_parado(self):
        # Lo que hace el juego de verdad (partida de prueba de la 2.0.0): la API del reloj ya contesta en la
        # pantalla de carga, con 0-1 s y sin avanzar, unos 30 s antes de que se pueda jugar.
        app, _, lol = montar()
        lol.fase, lol.segundos = "InProgress", None
        app.vigia.paso()
        for segundos in (0.02, 0.02, 0.3):
            lol.segundos = segundos
            app.actualizar_modo()
            self.assertEqual((app.modo, app.reloj), ("carga", None), segundos)
        lol.segundos = 1.1  # empieza la partida: el reloj avanza
        app.actualizar_modo()
        self.assertEqual((app.modo, app.reloj), ("juego", 1.1))

    def test_empezada_no_vuelve_a_la_carga(self):
        app, _, lol = montar()
        lol.fase, lol.segundos = "InProgress", 0.0
        app.vigia.paso()
        lol.segundos = 95.0
        app.actualizar_modo()
        self.assertEqual(app.modo, "juego")
        lol.segundos = None  # la API del juego no contesta a tiempo
        app.actualizar_modo()
        self.assertEqual((app.modo, app.reloj), ("juego", 95.0))
        lol.segundos = 95.0  # pausa: el reloj no avanza
        app.actualizar_modo()
        self.assertEqual(app.modo, "juego")
        lol.fase = "EndOfGame"
        app.vigia.paso()
        lol.fase, lol.segundos = "InProgress", 0.02  # la siguiente partida vuelve a empezar en la carga
        app.vigia.paso()
        self.assertEqual(app.modo, "carga")

    def test_el_overlay_no_cuenta_como_mirar_el_panel(self):
        app, _, _ = montar()
        app.ultima_consulta = 0
        app.estado(contar=False)
        self.assertEqual(app.ultima_consulta, 0)
        app.estado()
        self.assertGreater(app.ultima_consulta, 0)


class NormasDeRiot(unittest.TestCase):
    def test_en_flex_manda_el_rango_de_solo_duo(self):
        app, riot, lol = montar()
        riot.juego["gameQueueConfigId"] = 440
        lol.fase = "InProgress"
        app.vigia.paso()
        self.assertTrue(esperar(app.sesion))
        liga = app.estado()["panel"]["equipos"]["aliado"][0]["liga"]
        self.assertEqual((liga["solo"]["txt"], liga["flex"]["txt"]), ("Diamante IV", "Platino II"))

    def test_con_el_juego_empezado_solo_datos(self):
        app, _, lol = montar()
        lol.fase = "InProgress"
        app.vigia.paso()
        self.assertTrue(esperar(app.sesion))
        app.sesion.panel()
        app.sesion._sucio = False
        app.sesion._panel["plan"] = ["algo interpretativo"]
        app.sesion._panel["lineas"] = [
            {"linea": "top", "veredicto": "Aquí se equivocan", "tono": "bien", "rival": [], "aliado": []}
        ]
        self.assertTrue(app.estado()["panel"]["plan"])
        lol.segundos = 90.0
        app.actualizar_modo()
        p = app.estado()["panel"]
        self.assertEqual(p["plan"], [])
        self.assertEqual([(l["veredicto"], l["tono"]) for l in p["lineas"]], [("", "neutro")])
        self.assertTrue(all(a["tono"] == "neutro" for a in p["avisos"]))
        if p["jungla"]:
            self.assertTrue(all(t["tono"] == "neutro" for t in p["jungla"]["tarjetas"]))
        self.assertEqual(app.sesion._panel["plan"], ["algo interpretativo"])  # el original no se toca

    def test_premades_de_ambos_equipos_en_el_panel(self):
        from unittest import mock

        app, _, lol = montar()
        lol.fase = "InProgress"

        # Dos jugadores de cada equipo vienen juntos (los dos primeros de cada lista, sin contarme a mí).
        def con_grupo(equipo, muestras):
            return dict.fromkeys([x for x in equipo if x != "puuid-yo"][:2], 1)

        with mock.patch("deepprep.analisis.premades", side_effect=con_grupo):
            app.vigia.paso()
            self.assertTrue(esperar(app.sesion))
            p = app.estado()["panel"]
        for lado in ("aliado", "rival"):
            con = [f for f in p["equipos"][lado] if f["grupo"]]
            self.assertEqual(len(con), 2, lado)
            self.assertTrue(all(f["etiquetas"][0]["t"] == "Premade A" for f in con))
        self.assertFalse(next(f for f in p["equipos"]["aliado"] if f["soy_yo"])["grupo"])
        self.assertEqual(sum(a["texto"].startswith("Premade rival:") for a in p["avisos"]), 1)

    def test_duelo_contra_el_rival_directo_solo_antes_de_jugar(self):
        from tests.test_duelos import registro

        app, _, lol = montar()
        lol.fase = "InProgress"
        app.vigia.paso()
        self.assertTrue(esperar(app.sesion))
        yo = next(f for f in app.sesion.jugadores if f["puuid"] == "puuid-yo")
        rival = next(f for f in app.sesion.jugadores if f["equipo"] != yo["equipo"] and f["rol"] == yo["rol"])
        for i in range(12):
            app.duelos.guardar(
                f"KR_{i}", [dict(registro(i % 2), pos=yo["rol"], a=yo["campeon"], b=rival["campeon"], puuid=f"p{i}")]
            )
        app.sesion.invalidar_panel()
        d = app.estado()["panel"]["duelo"]
        self.assertEqual((d["n"], d["wr"], d["poco"]), (12, 50, False))
        lol.segundos = 90.0
        app.actualizar_modo()
        self.assertIsNone(app.estado()["panel"]["duelo"])

    def test_duelo_en_la_seleccion(self):
        from tests.test_duelos import registro

        app, _, lol = montar()
        app.datos.roles = {64: {"JUNGLE": 1.0}, 103: {"MIDDLE": 1.0}}
        for i in range(12):
            app.duelos.guardar(f"KR_{i}", [dict(registro(i % 3 == 0), puuid=f"p{i}")])
        lol.fase = "ChampSelect"
        lol.eleccion = {"mio": 131, "aliados": [], "rivales": [103, 64], "cola": 420, "pos": "JUNGLE"}
        app.vigia.paso()
        s = app.estado()["seleccion"]
        self.assertEqual((s["pos"], s["duelo"]["n"], s["duelo"]["wr"]), ("jungla", 12, 33))
        lol.eleccion = dict(lol.eleccion, rivales=[103])  # aún no ha elegido nadie de jungla
        app.vigia.paso()
        self.assertIsNone(app.estado()["seleccion"]["duelo"])

    def test_siempre_en_marcha_toca_el_arranque_con_windows(self):
        llamadas, error = [], [""]

        def arranque_windows(encendido):
            llamadas.append(encendido)
            return error[0]

        app, _, _ = montar(arranque_windows=arranque_windows)
        app.cfg["siempre_en_marcha"] = True
        self.assertTrue(app.guardar_ajustes({"siempre_en_marcha": True})["ok"])
        self.assertEqual(llamadas, [])  # sin cambio, no se toca
        self.assertTrue(app.guardar_ajustes({"siempre_en_marcha": False})["ok"])
        self.assertEqual((llamadas, app.cfg["siempre_en_marcha"]), ([False], False))
        error[0] = "falló"
        self.assertEqual(app.guardar_ajustes({"siempre_en_marcha": True}), {"ok": False, "error": "falló"})
        self.assertFalse(app.cfg["siempre_en_marcha"])

    def test_con_quien_compararte(self):
        from tests.test_duelos import registro

        app, _, _ = montar()
        guardar = lambda id_, puuid, g, m10: app.duelos.guardar(id_, [dict(registro(g, m10=m10), puuid=puuid)])  # noqa: E731
        for i in range(6):
            guardar(f"MIA_{i}", "puuid-yo", i % 2, 2)  # tus partidas: 2 muertes antes del 10 (3 victorias)
            guardar(f"CH_{i}", "chall", True, 0)
            guardar(f"OTP_{i}", "otp", True, 1)
        app.duelos.kv_set("ligas:kr", {"chall": "CHALLENGER", "otp": "MASTER"})
        app.duelos.kv_set("ref:otp#kr1", {"puuid": "otp", "plataforma": "kr", "rid": "Otp#KR1"})

        def muertes():
            d = app.duelo(131, "JUNGLE", 64)
            return d["tu"]["ref"], {f["que"]: f["ref"] for f in d["tu"]["filas"]}["Muertes antes del 10"]

        for modo, esperado in (("challenger", ("Challenger", "0,0")), ("mis_victorias", ("Tus victorias", "2,0"))):
            self.assertTrue(app.guardar_ajustes({"comparar_con": modo})["ok"])
            self.assertEqual(muertes(), esperado)
        self.assertTrue(app.guardar_ajustes({"referencias": {"131": "Otp#KR1"}})["ok"])
        self.assertEqual(
            muertes(), ("Otp contra Campeón 64", "1,0")
        )  # la referencia del campeón manda (y hay 5+ contra ese rival)
        self.assertEqual(app.comparador.para_el_recolector(), [{"puuid": "otp", "region": "asia", "campeon": 131}])
        self.assertFalse(app.guardar_ajustes({"comparar_con": "nadie"})["ok"])

    def test_perfil_de_base(self):
        from tests.test_duelos import registro

        app, _, _ = montar()
        self.assertFalse(app.guardar_ajustes({"comparar_con": "perfil", "perfil_base": ""})["ok"])  # sin jugador no vale
        app.duelos.kv_set("ref:pro#euw", {"puuid": "pro", "plataforma": "euw1", "rid": "Pro#EUW"})
        for i in range(3):
            app.duelos.guardar(f"PRO_{i}", [dict(registro(True, m10=1), puuid="pro")])  # Diana (131) en jungla
            app.duelos.guardar(
                f"MIA_{i}", [dict(registro(False, m10=2), puuid="puuid-yo"), dict(registro(False, m10=2), a=11, puuid="puuid-yo")]
            )
        self.assertTrue(app.guardar_ajustes({"comparar_con": "perfil", "perfil_base": "Pro#EUW"})["ok"])
        self.assertEqual(app.duelo(131, "JUNGLE", 64)["tu"]["ref"], "Pro con Campeón 131")
        # Con un campeón que él no juega: sus partidas en tu posición.
        self.assertEqual(app.duelo(11, "JUNGLE", 64)["tu"]["ref"], "Pro de jungla")
        self.assertIn({"puuid": "pro", "region": "europe", "campeon": None}, app.comparador.para_el_recolector())
        self.assertEqual(app.ajustes()["perfil_partidas"], 3)

    def test_region_del_cliente_y_primera_vez_sin_cuentas(self):
        app, riot, lol = montar()
        riot.poner_plataforma = lambda p, r: setattr(riot, "puesta", (p, r))
        lol.fase, lol.region = "Lobby", "na1"
        app.vigia.paso()
        self.assertEqual((app.cfg["plataforma"], app.cfg["region"], riot.puesta), ("na1", "americas", ("na1", "americas")))
        # Sin cuentas apuntadas (app recién instalada) basta con que la clave valga.
        riot.comprobar = lambda: {"id": "EUW1"}
        app.cfg["cuentas"] = []
        app.comprobar_clave()

    def test_ningun_texto_da_ordenes(self):
        from deepprep import sesion

        codigo = Path(sesion.__file__).read_text(encoding="utf-8").lower()
        for orden in ("evita", "no cuentes", "a explotar", "solo con compañeros"):
            self.assertNotIn(orden, codigo)


class Grabacion(unittest.TestCase):
    def test_una_vez_por_partida_y_solo_en_la_grieta(self):
        app, _, lol = montar()
        self.assertIsNone(app.estado()["grabacion"])
        for fase in ("ChampSelect", "GameStart", "InProgress", "InProgress"):
            lol.fase = fase
            app.vigia.paso()
        self.assertEqual(app.grabador.armados, 1)
        self.assertEqual(app.estado()["grabacion"], {"carpeta": "", "parada": False})

        lol.fase = "EndOfGame"
        app.vigia.paso()
        lol.fase, lol.mapa_id = "InProgress", 12  # ARAM
        app.vigia.paso()
        self.assertEqual(app.grabador.armados, 1)

        lol.fase = "Lobby"
        app.vigia.paso()
        lol.fase, lol.mapa_id = "InProgress", 0  # mapa desconocido: se graba por si acaso
        app.vigia.paso()
        self.assertEqual(app.grabador.armados, 2)

    def test_apagada_en_la_configuracion(self):
        cfg = dict(config.POR_DEFECTO, cuentas=["Yo#EUW"], grabar=False)
        app = crear(cfg, RiotFalso(None), LolFalso())
        self.assertIsNone(app.grabador)
        self.assertIsNone(app.estado()["grabacion"])


class RevisionYAjustes(unittest.TestCase):
    def test_revision_al_acabar(self):
        import gzip

        app, riot, _ = montar()
        with gzip.open(DATOS / "partida.json.gz", "rt", encoding="utf-8") as f:
            riot.crudo = json.load(f)
        with gzip.open(DATOS / "linea.json.gz", "rt", encoding="utf-8") as f:
            riot.crudo_linea = json.load(f)
        diana = next(p for p in riot.crudo["info"]["participants"] if p["championId"] == 131)
        rev = app.revisor.revisar(123, diana["puuid"], {"gank": None, "lineas": []}, None, intentos=1, pausa=0)
        self.assertEqual(riot.pedida, "EUW1_123")
        self.assertTrue(app.duelos.vista(riot.crudo["metadata"]["matchId"]))  # la partida también entra en tus duelos
        self.assertEqual(len(rev["muertes"]), diana["deaths"])
        id_ = riot.crudo["metadata"]["matchId"]
        self.assertEqual(app.ultima_revision, id_)
        lista = app.revisiones()["lista"]
        self.assertEqual((lista[0]["id"], lista[0]["campeon"]), (id_, "Campeón 131"))
        self.assertEqual(app.revision(id_)["kda"], rev["kda"])
        json.dumps(app.revisiones())

    def test_revision_sin_publicar(self):
        app, _, _ = montar()
        self.assertIsNone(app.revisor.revisar(1, "puuid-yo", None, None, intentos=2, pausa=0))

    def test_ajustes(self):
        app, _, _ = montar()
        self.assertFalse(app.guardar_ajustes({"atajo_overlay": "ctrl+nada"})["ok"])
        self.assertFalse(app.guardar_ajustes({"cuentas": ["sin-tag"]})["ok"])
        self.assertTrue(
            app.guardar_ajustes(
                {"atajo_overlay": "Alt+X", "overlay_opacidad": 3, "notas": {"11": " no pelear solo ", "64": "  "}}
            )["ok"]
        )
        self.assertEqual(
            (app.cfg["atajo_overlay"], app.cfg["overlay_opacidad"], app.cfg["notas"]), ("alt+x", 1.0, {"11": "no pelear solo"})
        )
        self.assertEqual(
            app.notas_de([11, 64, 11], rivales={11}),
            [{"campeon": "Campeón 11", "icono": "", "texto": "no pelear solo", "rival": True}],
        )
        self.assertIn("campeones", app.ajustes())

    def test_recuerda_la_cuenta_secundaria(self):
        app, _, lol = montar()
        lol.fase = "Lobby"
        lol.nombre = "Otro"
        app.vigia.paso()
        self.assertEqual(app.cfg["cuentas"], ["Yo#EUW", "Otro#EUW"])
        app.vigia.paso()
        self.assertEqual(len(app.cfg["cuentas"]), 2)


class SeleccionDeCampeon(unittest.TestCase):
    def test_historial_contra_lo_que_eligen(self):
        app, _, lol = montar()

        def jug(puuid, equipo, campeon, gana):
            return {
                "puuid": puuid,
                "equipo": equipo,
                "campeon": campeon,
                "pos": "JUNGLE",
                "gana": gana,
                "pid": 1,
                "nombre": puuid,
                "tag": "",
                "k": 0,
                "d": 0,
                "a": 0,
                "ch": {},
            }

        ahora = int(time.time() * 1000)
        for i, (cola, gana) in enumerate([(420, True), (420, False), (440, True)]):
            app.cache.guardar_partida(
                {
                    "id": f"m{i}",
                    "creacion": ahora - i,
                    "duracion": 1800,
                    "cola": cola,
                    "mapa": 11,
                    "remake": False,
                    "equipos": {},
                    "jug": [jug("puuid-yo", 100, 131, gana), jug("r", 200, 11, not gana)],
                }
            )
        lol.fase = "ChampSelect"
        lol.eleccion = {"mio": 131, "aliados": [], "rivales": [11], "cola": 420}
        app.vigia.paso()
        sel = app.estado()["seleccion"]
        json.dumps(sel)
        self.assertEqual(sel["mio"]["nombre"], "Campeón 131")
        h = sel["historial"]
        # La flexible no cuenta en una selección de solo/dúo.
        self.assertEqual((h["n"], h["campeon"]["v"], h["cola_txt"]), (2, 1, " de solo/dúo"))
        self.assertEqual((h["vs"][0]["n"], h["vs"][0]["v"]), (2, 1))
        lol.fase = "Lobby"
        app.vigia.paso()
        self.assertIsNone(app.estado()["seleccion"])


class RecolectorPorRegion(unittest.TestCase):
    def test_tu_region_va_con_el_cliente_del_panel_y_las_demas_aparte(self):
        for region in ("europe", "asia"):
            with self.subTest(region=region):
                cfg = dict(config.POR_DEFECTO, cuentas=["Yo#EUW"], region=region, revisar=False, grabar=False)
                riot = RiotFalso(None)
                app = crear(cfg, riot, LolFalso())
                with (
                    mock.patch.object(rec.config, "cargar", dict),
                    mock.patch.object(rec.Recolector, "arrancar", return_value=True),
                ):
                    app._arrancar_recolector()
                r = app.recolector
                assert r is not None
                self.assertIs(r.cliente_propio, riot)  # comparte cuota con el panel: solo con el cliente quieto
                self.assertEqual(r.cuota_libre, app._cuota_libre)
                fuera = sorted(c.region for c in r.clientes)
                self.assertEqual(len(fuera), len(rec.TODAS) - 1)
                self.assertNotIn(f"{region}.api.riotgames.com", fuera)  # la tuya no va dos veces
                self.assertEqual(rec.de_fuera(region), [(p, x) for p, x in rec.TODAS if x != region])


class BusquedaManual(unittest.TestCase):
    def test_buscar_y_volver(self):
        app, _, lol = montar()
        lol.fase = "Lobby"
        self.assertFalse(app.buscar("Nadie#EUW")["ok"])
        self.assertFalse(app.buscar("sin-almohadilla")["ok"])
        self.assertTrue(app.buscar("Otro#EUW")["ok"])
        self.assertEqual((app.sesion.origen, app.sesion.yo, app.sesion.mi_equipo), ("manual", "puuid-otro", 200))
        self.assertEqual(app.estado()["panel"]["recordatorios"], [])
        app.volver()
        self.assertIsNone(app.sesion)

    def test_la_busqueda_no_se_pisa_hasta_la_siguiente_partida(self):
        app, _, lol = montar()
        lol.fase = "InProgress"
        app.vigia.paso()
        app.buscar("Otro#EUW")
        manual = app.sesion
        app.vigia.ultimo_sondeo = 0
        app.vigia.paso()
        self.assertIs(app.sesion, manual)
        lol.fase = "Lobby"
        app.vigia.paso()
        lol.fase = "InProgress"
        app.vigia.ultimo_sondeo = 0
        app.vigia.paso()
        self.assertEqual(app.sesion.origen, "propia")


class Clave(unittest.TestCase):
    def test_formato_y_reintento(self):
        app, riot, _ = montar()
        self.assertFalse(app.poner_clave("hola")["ok"])
        riot.clave_mala = True
        guardar, config.guardar_clave = config.guardar_clave, lambda clave: None
        try:
            self.assertEqual(app.poner_clave("RGAPI-nueva"), {"ok": True, "pendiente": True})
            self.assertFalse(app.estado()["clave"]["ok"])
            riot.clave_mala = False
            app.mis_cuentas.ultima_prueba = 0
            app.vigia.paso()
            self.assertTrue(app.estado()["clave"]["ok"])
        finally:
            config.guardar_clave = guardar


class Web(unittest.TestCase):
    PUERTO = 5959
    app: App
    srv: servidor.Servidor

    @classmethod
    def setUpClass(cls):
        import threading

        cls.app, _, _ = montar()
        cls.srv = servidor.crear(cls.app, cls.PUERTO)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def pedir(self, ruta, cuerpo=None, cabeceras=None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        pet = urllib.request.Request(f"http://127.0.0.1:{self.PUERTO}{ruta}", data=datos, headers=cabeceras or {})
        try:
            with urllib.request.urlopen(pet, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_paginas_y_estado(self):
        for ruta in ("/", "/js/main.js", "/estilo.css"):
            self.assertEqual(self.pedir(ruta)[0], 200)
        for ruta in ("/app.js", "/js/no-existe.js", "/js/..%2Fservidor.py", "/js/../app.py"):
            self.assertEqual(self.pedir(ruta)[0], 404)
        codigo, cuerpo = self.pedir("/api/estado")
        self.assertEqual(codigo, 200)
        self.assertIn("fase_txt", json.loads(cuerpo))
        self.assertEqual(self.pedir("/no-existe")[0], 404)

    def test_otra_web_no_puede_tocar_la_app(self):
        ajena = {"Origin": "https://ejemplo.com"}
        self.assertEqual(self.pedir("/api/clave", {"clave": "RGAPI-x"}, ajena)[0], 403)
        self.assertEqual(self.pedir("/api/estado", None, {"Host": "ejemplo.com"})[0], 403)
        propio = {"Origin": f"http://127.0.0.1:{self.PUERTO}"}
        codigo, cuerpo = self.pedir("/api/buscar", {"riot_id": "mal"}, propio)
        self.assertEqual((codigo, json.loads(cuerpo)["ok"]), (200, False))


if __name__ == "__main__":
    unittest.main()
