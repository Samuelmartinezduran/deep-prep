"""Pruebas del modo demo (py -m deepprep --demo): se monta sin clave ni red, cada escena da un estado como el de la
app de verdad, en partida quita lo mismo que ella y no escribe nada fuera de su carpeta temporal."""

import datetime
import http.client
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from deepprep import config, demo, inicio_windows, servidor
from deepprep.app import App
from tests import registro_de
from tests.test_app import esperar, montar

RAIZ = Path(__file__).resolve().parent.parent
# Un jueves a las 22:00 (hora local): las revisiones de ejemplo son de hace 37 y 75 minutos, las dos de hoy.
AHORA = datetime.datetime(2026, 11, 5, 22, 0).timestamp()
DDRAGON = "https://ddragon.leagueoflegends.com/"


class SinRed(unittest.TestCase):
    """La demo con la red y los procesos de fuera cortados: urlopen falla y apunta qué se ha pedido."""

    def setUp(self):
        self.pedidas: list[str] = []

        def sin_red(pet, *args, **kw):
            self.pedidas.append(getattr(pet, "full_url", pet))
            raise OSError("sin red en las pruebas de la demo")

        for objetivo, efecto in (
            ("urllib.request.urlopen", sin_red),
            ("subprocess.Popen", AssertionError("la demo no lanza procesos")),
            ("subprocess.run", AssertionError("la demo no lanza procesos")),
            ("os.startfile", AssertionError("la demo no abre archivos")),
        ):
            parche = mock.patch(objetivo, side_effect=efecto, create=True)
            parche.start()
            self.addCleanup(parche.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.carpeta = Path(tmp.name)
        self.app = demo.AppDemo(self.carpeta, ahora=AHORA)

    def estado(self, escena):
        self.assertEqual(self.app.elegir_escena(escena), {"ok": True})
        e = self.app.estado()
        json.dumps(e)  # tiene que poder viajar como JSON al panel
        return e


class Montaje(SinRed):
    def test_se_monta_sin_clave_ni_red(self):
        for escena in demo.ESCENAS:
            e = self.estado(escena)
            self.assertEqual(e["clave"], {"ok": True, "error": ""})  # sin el aviso de pegar la clave
            self.assertEqual(e["cuota"]["usadas"], 0)
            self.assertIsNone(e["grabacion"])
            self.assertEqual(e["demo"], {"escena": escena})
        self.app.revisiones()
        self.app.ajustes()
        self.assertEqual(self.pedidas, [])
        self.assertEqual(list(self.carpeta.iterdir()), [])  # hasta que no se guarda nada, no escribe nada

    def test_cada_escena_da_un_estado_como_el_de_la_app(self):
        real, _, lol = montar()
        lol.fase = "InProgress"
        real.vigia.paso()
        self.assertTrue(esperar(real.sesion))
        en_partida = real.estado()
        lol.fase, lol.eleccion = "ChampSelect", {"mio": 131, "aliados": [], "rivales": [11], "cola": 420, "pos": "JUNGLE"}
        real.vigia.paso()
        en_seleccion = real.estado()

        seleccion = self.estado("seleccion")
        self.assertEqual(set(seleccion), set(en_partida) | {"demo"})
        self.assertEqual((seleccion["fase_txt"], seleccion["modo"], seleccion["panel"]), ("Selección de campeón", "previa", None))
        self.assertEqual(set(seleccion["seleccion"]), set(en_seleccion["seleccion"]))
        self.assertTrue(seleccion["seleccion"]["duelo"] and seleccion["seleccion"]["pool"]["filas"])

        carga = self.estado("carga")
        self.assertEqual(
            (carga["fase_txt"], carga["modo"], carga["reloj"], carga["seleccion"]), ("En partida", "carga", None, None)
        )
        self.assertEqual(set(carga["panel"]), set(en_partida["panel"]))
        p = carga["panel"]
        self.assertEqual((len(p["equipos"]["aliado"]), len(p["equipos"]["rival"])), (5, 5))
        self.assertEqual([f["nombre"] for f in p["equipos"]["aliado"] if f["soy_yo"]], ["Driftmark"])
        self.assertTrue(all(f["tag"] == "DEMO" for f in p["equipos"]["aliado"] + p["equipos"]["rival"]))

        juego = self.estado("juego")
        self.assertEqual((juego["modo"], juego["reloj"]), ("juego", demo.RELOJ))

    def test_escena_que_no_existe(self):
        self.app.elegir_escena("juego")
        self.assertFalse(self.app.elegir_escena("revisiones")["ok"])  # es una pestaña del panel, no una escena
        self.assertEqual(self.app.escena, "juego")
        self.assertEqual(demo.AppDemo(self.carpeta, escena="otra").escena, demo.ESCENA_INICIAL)

    def test_el_overlay_no_cuenta_como_mirar_el_panel(self):
        self.app.ultima_consulta = 0
        self.app.estado(contar=False)
        self.assertEqual(self.app.ultima_consulta, 0)
        self.app.estado()
        self.assertGreater(self.app.ultima_consulta, 0)


class EnPartida(SinRed):
    def test_quita_lo_mismo_que_la_app(self):
        carga = self.estado("carga")["panel"]
        juego = self.estado("juego")["panel"]
        # Lo que hace la app de verdad con el juego empezado, con el mismo panel.
        app: Any = types.SimpleNamespace(modo="juego")
        self.assertEqual(juego, App._para_el_modo(app, carga))
        # Y que la prueba diga algo: antes de jugar había de todo, y ya jugando se ha ido.
        self.assertTrue(carga["plan"] and carga["duelo"] and carga["jungla"]["mapa"])
        self.assertTrue(any(l["veredicto"] for l in carga["lineas"]))
        self.assertTrue(any(a["tono"] != "neutro" for a in carga["avisos"]))
        self.assertEqual((juego["plan"], juego["duelo"], juego["jungla"]["mapa"]), ([], None, {}))
        self.assertEqual({(l["veredicto"], l["tono"]) for l in juego["lineas"]}, {("", "neutro")})
        self.assertEqual({a["tono"] for a in juego["avisos"]}, {"neutro"})
        self.assertEqual({t["tono"] for t in juego["jungla"]["tarjetas"]}, {"neutro"})
        self.assertEqual(juego["equipos"], carga["equipos"])  # los datos de los jugadores se quedan

    def test_el_panel_de_ejemplo_no_se_toca(self):
        self.estado("juego")
        self.assertTrue(self.estado("carga")["panel"]["plan"])


class Revisiones(SinRed):
    def test_revisiones_de_ejemplo(self):
        r = self.app.revisiones()
        self.assertEqual(
            [(x["campeon"], x["gana"], x["lp"]) for x in r["lista"]], [("Diana", False, -19), ("Maestro Yi", True, 21)]
        )
        fechas = [x["fecha"] for x in r["lista"]]
        self.assertEqual(fechas, sorted(fechas, reverse=True))
        hoy = datetime.datetime.fromtimestamp(AHORA).date()
        self.assertTrue(all(datetime.datetime.fromtimestamp(f / 1000).date() == hoy for f in fechas))
        self.assertTrue(r["tendencias"]["n"] and r["tendencias"]["rivales"])
        muertes = 0
        for fila in r["lista"]:
            rev = self.app.revision(fila["id"])
            assert rev is not None
            self.assertEqual(rev["kda"], fila["kda"])
            self.assertTrue(rev["objetivos"] and rev["prevision"] and rev["referencia"] and rev["comparacion"])
            self.assertTrue(all(m["clip"] and "x" in m for m in rev["muertes"]))
            muertes += len(rev["muertes"])
        self.assertEqual(len(r["muertes"]), muertes)  # el mapa de muertes sale de todas
        self.assertIsNone(self.app.revision("EUW1_1"))

    def test_sin_grabaciones_ni_busquedas(self):
        rev = self.app.revisiones()["lista"][0]["id"]
        for r in (
            self.app.abrir_clip(rev, 0),
            self.app.abrir_carpeta(rev),
            self.app.buscar("Alguien#EUW"),
            self.app.poner_clave("RGAPI-x"),
        ):
            self.assertFalse(r["ok"])
            self.assertTrue(r["error"])
        self.assertEqual(self.app.volver(), {"ok": True})
        self.assertEqual(self.pedidas, [])


class AjustesDeLaDemo(SinRed):
    def test_guardar_va_a_su_carpeta_y_se_ve_en_el_panel(self):
        self.assertEqual(
            self.app.guardar_ajustes({"notas": {"131": "Busca el 6 antes del dragón"}, "recordatorios": ["Una regla"]}),
            {"ok": True},
        )
        self.assertEqual([p.name for p in self.carpeta.iterdir()], ["config.json"])
        guardado = json.loads((self.carpeta / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(guardado["notas"], {"131": "Busca el 6 antes del dragón"})
        p = self.estado("carga")["panel"]
        self.assertEqual([(n["campeon"], n["texto"]) for n in p["notas"]], [("Diana", "Busca el 6 antes del dragón")])
        self.assertEqual(p["recordatorios"], ["Una regla"])
        self.assertEqual(self.estado("seleccion")["seleccion"]["notas"][0]["texto"], "Busca el 6 antes del dragón")
        self.assertEqual(self.app.ajustes()["recordatorios"], ["Una regla"])

    def test_se_comprueba_como_en_la_app(self):
        self.assertFalse(self.app.guardar_ajustes({"atajo_overlay": "nada+raro"})["ok"])
        self.assertFalse(self.app.guardar_ajustes({"referencias": {"131": "SinTag"}})["ok"])
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_referencias_y_arranque_sin_riot_ni_windows(self):
        a = self.app.ajustes()
        self.assertEqual((a["referencias_partidas"], a["perfil_partidas"]), ({"131": 47}, None))
        cambios = {"siempre_en_marcha": False, "comparar_con": "perfil", "perfil_base": "Nightjar#DEMO"}
        self.assertEqual(self.app.guardar_ajustes(dict(cambios, referencias={"131": "Otro#DEMO"})), {"ok": True})
        a = self.app.ajustes()
        self.assertEqual((a["referencias_partidas"], a["perfil_partidas"]), ({"131": None}, 112))
        self.assertFalse(inicio_windows.ACCESO.exists())
        self.assertEqual(self.app.guardar_ajustes({"siempre_en_marcha": True}), {"ok": True})
        self.assertFalse(inicio_windows.ACCESO.exists())  # el arranque con Windows no se toca
        self.assertEqual(self.pedidas, [])

    def test_salir(self):
        self.assertFalse(self.app.salir()["ok"])  # sin ventanas ni nadie que la cierre
        cerrada = threading.Event()
        self.app.al_salir = cerrada.set
        self.assertEqual(self.app.salir(), {"ok": True})
        self.assertTrue(cerrada.wait(5))


def pedir(puerto, ruta, cuerpo=None, cabeceras=None):
    """Petición al servidor local con http.client (no pasa por urlopen, que en estas pruebas falla)."""
    con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
    try:
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        con.request("GET" if cuerpo is None else "POST", ruta, body=datos, headers=cabeceras or {})
        r = con.getresponse()
        return r.status, r.read()
    finally:
        con.close()


class ServidorDeLaDemo(SinRed):
    def setUp(self):
        super().setUp()
        self.srv = servidor.crear(self.app, 0, post=self.app.rutas())  # 0: un puerto libre
        self.puerto = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def json(self, ruta, cuerpo=None):
        codigo, datos = pedir(self.puerto, ruta, cuerpo)
        self.assertEqual(codigo, 200, ruta)
        return json.loads(datos)

    def test_el_panel_entero(self):
        for ruta in ("/", "/js/main.js", "/js/demo.js", "/estilo.css"):
            self.assertEqual(pedir(self.puerto, ruta)[0], 200, ruta)
        self.assertEqual(self.json("/api/estado")["demo"], {"escena": demo.ESCENA_INICIAL})
        self.assertEqual(self.json("/api/demo", {"escena": "juego"}), {"ok": True})
        self.assertEqual(self.json("/api/estado?vista=overlay")["modo"], "juego")
        self.assertFalse(self.json("/api/demo", {"escena": "no"})["ok"])
        revisiones = self.json("/api/revisiones")
        self.assertEqual(self.json(f"/api/revision?id={revisiones['lista'][0]['id']}")["campeon"], "Diana")
        self.assertIn("Larkspur#DEMO", self.json("/api/ajustes")["referencias"].values())
        self.assertEqual(self.json("/api/ajustes", {"atajo_overlay": "alt+x"}), {"ok": True})
        self.assertEqual(self.json("/api/novedades", {}), {"ok": True})
        self.assertFalse(self.json("/api/clave", {"clave": "RGAPI-x"})["ok"])
        self.assertEqual(self.pedidas, [])

    def test_sin_red_las_imagenes_no_estan_y_nada_se_rompe(self):
        self.assertEqual(pedir(self.puerto, "/ddragon/campeon/Diana.png")[0], 404)
        self.assertEqual(len(self.pedidas), 1)
        self.assertTrue(self.pedidas[0].startswith(DDRAGON), self.pedidas)  # lo único de fuera: Data Dragon
        self.assertEqual(self.json("/api/estado")["clave"]["ok"], True)

    def test_otra_web_no_cambia_la_escena(self):
        ajena = {"Origin": "https://ejemplo.com", "Content-Type": "application/json"}
        self.assertEqual(pedir(self.puerto, "/api/demo", {"escena": "juego"}, ajena)[0], 403)
        self.assertEqual(self.app.escena, demo.ESCENA_INICIAL)

    def test_la_app_de_verdad_no_tiene_escenas(self):
        real, _, _ = montar()
        srv = servidor.crear(real, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.assertEqual(pedir(srv.server_address[1], "/api/demo", {"escena": "juego"})[0], 404)
        finally:
            srv.shutdown()
            srv.server_close()


class CarpetaDeLaDemo(unittest.TestCase):
    def test_la_elige_config_y_manda_sobre_deepprep_datos(self):
        carpeta = config.elegir_datos({"DEEPPREP_DATOS": str(RAIZ)}, ["DeepPrep.exe", "--demo"])
        try:
            self.assertTrue(config.es_carpeta_demo(carpeta))
            self.assertNotEqual(carpeta, RAIZ)
            self.assertEqual(list(carpeta.iterdir()), [])
        finally:
            self.assertTrue(demo.borrar_carpeta(carpeta))
        self.assertFalse(carpeta.exists())

    def test_solo_borra_carpetas_de_la_demo(self):
        with tempfile.TemporaryDirectory() as otra, registro_de("deepprep.demo") as registro:
            self.assertFalse(demo.borrar_carpeta(Path(otra)))
            self.assertTrue(Path(otra).is_dir())
            self.assertFalse(demo.borrar_carpeta(RAIZ))
        self.assertTrue((RAIZ / "pyproject.toml").is_file())
        self.assertEqual(registro.getvalue().count("no es una carpeta de la demo"), 2)


# Lo que la app escribe en su carpeta de datos (desde el código, la del proyecto): la demo no puede crear nada de esto.
DATOS_DE_LA_APP = (
    "clave.txt",
    "config.json",
    "config.json.copia",
    "cache.db",
    "duelos.db",
    "deepprep.log",
    "imagenes",
    "novedades.json",
    "version_vista.txt",
    "actualizacion",
)


def huella(carpeta):
    """Los archivos de una carpeta (sin entrar en las de dentro) con su tamaño y su fecha de cambio."""
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in carpeta.iterdir() if p.is_file()}


class LaDemoEntera(unittest.TestCase):
    """py -m deepprep --demo --sin-ventana de verdad, en otro proceso, con DEEPPREP_DATOS apuntando a un centinela."""

    def test_no_escribe_fuera_de_su_carpeta_y_la_borra_al_salir(self):
        with tempfile.TemporaryDirectory() as raiz_prueba:
            centinela, temporal = Path(raiz_prueba) / "centinela", Path(raiz_prueba) / "temp"
            centinela.mkdir()
            temporal.mkdir()
            carpetas = (RAIZ, RAIZ / "deepprep", RAIZ / "deepprep" / "demo")
            antes = {c: huella(c) for c in carpetas}
            habia = {n for n in DATOS_DE_LA_APP if (RAIZ / n).exists()}
            entorno = dict(
                os.environ,
                DEEPPREP_DATOS=str(centinela),
                TEMP=str(temporal),
                TMP=str(temporal),
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONUTF8="1",
            )
            proc = subprocess.Popen(
                [sys.executable, "-m", "deepprep", "--demo", "--sin-ventana", "--puerto", "0"],
                cwd=RAIZ,
                env=entorno,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            salida = proc.stderr
            assert salida is not None
            lineas: queue.Queue[str] = queue.Queue()

            def leer():
                for linea in salida:
                    lineas.put(linea)

            threading.Thread(target=leer, daemon=True).start()
            try:
                puerto = self._puerto(lineas)
                (carpeta,) = list(temporal.iterdir())  # la suya, nueva, en la carpeta temporal del sistema
                self.assertTrue(carpeta.name.startswith(config.PREFIJO_DEMO))
                origen = {"Origin": f"http://127.0.0.1:{puerto}", "Content-Type": "application/json"}
                for escena in ("seleccion", "juego", "carga"):
                    self.assertEqual(pedir(puerto, "/api/demo", {"escena": escena}, origen)[0], 200)
                    self.assertEqual(json.loads(pedir(puerto, "/api/estado")[1])["demo"]["escena"], escena)
                for ruta in ("/api/revisiones", "/api/ajustes", "/api/estado?vista=overlay"):
                    self.assertEqual(pedir(puerto, ruta)[0], 200, ruta)
                codigo, cuerpo = pedir(puerto, "/api/ajustes", {"notas": {"131": "Nota de prueba"}}, origen)
                self.assertEqual((codigo, json.loads(cuerpo)), (200, {"ok": True}))
                self.assertTrue((carpeta / "config.json").is_file())
                self.assertEqual(json.loads(pedir(puerto, "/api/salir", {}, origen)[1]), {"ok": True})
                self.assertEqual(proc.wait(timeout=30), 0)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                salida.close()
            self.assertEqual(list(temporal.iterdir()), [])  # su carpeta se ha borrado al salir
            self.assertEqual(list(centinela.iterdir()), [])  # DEEPPREP_DATOS ni se ha tocado
            self.assertEqual({c: huella(c) for c in carpetas}, antes)  # ni la carpeta del proyecto
            self.assertEqual({n for n in DATOS_DE_LA_APP if (RAIZ / n).exists()}, habia)

    def _puerto(self, lineas):
        limite = time.time() + 60
        visto = []
        while time.time() < limite:
            try:
                linea = lineas.get(timeout=1)
            except queue.Empty:
                continue
            visto.append(linea)
            m = re.search(r"http://127\.0\.0\.1:(\d+)/", linea)
            if m:
                return int(m.group(1))
        self.fail(f"la demo no ha dicho en qué puerto está: {''.join(visto)}")


if __name__ == "__main__":
    unittest.main()
