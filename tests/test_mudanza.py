"""Paso de Porofesor (1.0.x) a Deep Prep: datos, instalación, accesos directos y zip puente.

Todo pasa en carpetas temporales: ni los datos, ni el programa, ni los accesos directos de verdad se tocan.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from deepprep import __version__, config, inicio_windows
from deepprep import actualizador as act

RAIZ = Path(__file__).resolve().parent.parent
NOTAS = "- Porofesor ahora se llama Deep Prep"


def datos_de_porofesor(carpeta):
    """Una carpeta de datos como la de la 1.0.2 justo después de bajarse la 2.0.0."""
    carpeta.mkdir(parents=True)
    (carpeta / "config.json").write_text(json.dumps({"cuentas": ["Yo#EUW"], "siempre_en_marcha": True}), encoding="utf-8")
    (carpeta / "clave.txt").write_text("RGAPI-prueba", encoding="utf-8")
    (carpeta / "cache.db").write_bytes(b"SQLite format 3\0")
    (carpeta / "porofesor.log").write_text("Porofesor en http://127.0.0.1:5151/\n", encoding="utf-8")
    (carpeta / "recolector.lock").write_text("", encoding="utf-8")
    (carpeta / "imagenes" / "campeon").mkdir(parents=True)
    (carpeta / "imagenes" / "campeon" / "1.png").write_bytes(b"png")
    # Lo que deja el actualizador de la 1.0.2 al bajar la versión nueva: sus notas y la descarga.
    (carpeta / "novedades.json").write_text(json.dumps({"version": __version__, "notas": NOTAS}), encoding="utf-8")
    (carpeta / "version_vista.txt").write_text("1.0.2", encoding="utf-8")
    (carpeta / "actualizacion" / "nueva" / "DeepPrep").mkdir(parents=True)
    (carpeta / "actualizacion" / "nueva" / "DeepPrep" / "Porofesor.exe").write_bytes(b"MZ")


class ConCarpetaTemporal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.avisos = len(config.AVISOS)

    def tearDown(self):
        del config.AVISOS[self.avisos:]
        self._tmp.cleanup()


class MudanzaDeDatos(ConCarpetaTemporal):
    def setUp(self):
        super().setUp()
        self.viejos, self.nuevos = self.tmp / "Porofesor", self.tmp / "DeepPrep"

    def test_mueve_la_carpeta(self):
        datos_de_porofesor(self.viejos)
        self.assertEqual(config.mudar_datos(self.viejos, self.nuevos, pausa=0), self.nuevos)
        self.assertFalse(self.viejos.exists())
        self.assertEqual((self.nuevos / "clave.txt").read_text(encoding="utf-8"), "RGAPI-prueba")
        self.assertEqual(json.loads((self.nuevos / "config.json").read_text(encoding="utf-8"))["cuentas"], ["Yo#EUW"])
        self.assertTrue((self.nuevos / "imagenes" / "campeon" / "1.png").is_file())
        self.assertFalse((self.nuevos / "actualizacion").exists())  # la descarga ya instalada no se muda
        self.assertIn("movidos", config.AVISOS[-1])

    def test_no_toca_nada_si_ya_hay_datos_de_deep_prep(self):
        datos_de_porofesor(self.viejos)
        self.nuevos.mkdir()
        (self.nuevos / "config.json").write_text("{}", encoding="utf-8")
        self.assertEqual(config.mudar_datos(self.viejos, self.nuevos, pausa=0), self.nuevos)
        self.assertEqual((self.nuevos / "config.json").read_text(encoding="utf-8"), "{}")
        self.assertFalse((self.nuevos / "clave.txt").exists())
        self.assertTrue((self.viejos / "clave.txt").is_file())
        self.assertTrue((self.viejos / "actualizacion").is_dir())

    def test_sin_porofesor_no_hace_nada(self):
        self.assertEqual(config.mudar_datos(self.viejos, self.nuevos, pausa=0), self.nuevos)
        self.assertFalse(self.nuevos.exists())

    def test_copia_si_no_se_puede_mover(self):
        datos_de_porofesor(self.viejos)
        # Un archivo abierto (como el registro de la versión que se está cerrando): Windows no deja cambiar el nombre.
        with open(self.viejos / "porofesor.log", "a", encoding="utf-8"):
            self.assertEqual(config.mudar_datos(self.viejos, self.nuevos, intentos=2, pausa=0), self.nuevos)
        self.assertTrue((self.viejos / "config.json").is_file())  # la vieja se queda como estaba
        for nombre in ("config.json", "clave.txt", "cache.db", "novedades.json", "version_vista.txt", "porofesor.log"):
            self.assertEqual((self.nuevos / nombre).read_bytes(), (self.viejos / nombre).read_bytes(), nombre)
        self.assertTrue((self.nuevos / "imagenes" / "campeon" / "1.png").is_file())
        self.assertFalse((self.nuevos / "recolector.lock").exists())
        self.assertFalse((self.nuevos / "actualizacion").exists())
        self.assertIn("copiados", config.AVISOS[-1])

    def test_si_tampoco_se_puede_copiar_sigue_con_la_vieja(self):
        datos_de_porofesor(self.viejos)
        with mock.patch("deepprep.config.os.rename", side_effect=PermissionError("en uso")), \
                mock.patch("deepprep.config.shutil.copytree", side_effect=OSError("disco lleno")):
            self.assertEqual(config.mudar_datos(self.viejos, self.nuevos, intentos=2, pausa=0), self.viejos)
        self.assertFalse((self.nuevos / "config.json").exists())  # así se vuelve a intentar en el próximo arranque
        self.assertTrue((self.viejos / "clave.txt").is_file())

    def test_completa_una_carpeta_nueva_sin_config(self):
        datos_de_porofesor(self.viejos)
        self.nuevos.mkdir()
        (self.nuevos / "deepprep.log").write_text("algo\n", encoding="utf-8")
        self.assertEqual(config.mudar_datos(self.viejos, self.nuevos, pausa=0), self.nuevos)
        self.assertTrue((self.nuevos / "config.json").is_file())
        self.assertTrue((self.nuevos / "clave.txt").is_file())
        self.assertEqual((self.nuevos / "deepprep.log").read_text(encoding="utf-8"), "algo\n")

    def test_las_novedades_salen_despues_de_mudar(self):
        datos_de_porofesor(self.viejos)
        config.mudar_datos(self.viejos, self.nuevos, pausa=0)
        with mock.patch.object(act, "NOVEDADES", self.nuevos / "novedades.json"), \
                mock.patch.object(act, "VISTA", self.nuevos / "version_vista.txt"):
            a = act.Actualizador(app=None)
            self.assertEqual(a.novedades()["notas"], NOTAS)
            self.assertFalse(a._faltan_novedades())  # están: no hay que pedírselas a GitHub


class QuienMudaLosDatos(ConCarpetaTemporal):
    def setUp(self):
        super().setUp()
        self.viejos, self.nuevos = self.tmp / "Porofesor", self.tmp / "DeepPrep"
        self.programa = self.tmp / "Programs" / "DeepPrep"
        self.parches = [mock.patch.object(config, "CONGELADA", True), mock.patch.object(config, "PROGRAMA", self.programa),
                        mock.patch.object(config, "RAIZ", self.programa)]
        for p in self.parches:
            p.start()
        self.entorno = {"LOCALAPPDATA": str(self.tmp)}

    def tearDown(self):
        for p in reversed(self.parches):
            p.stop()
        super().tearDown()

    def test_la_copia_instalada_los_muda(self):
        datos_de_porofesor(self.viejos)
        self.assertEqual(config.elegir_datos(self.entorno, ["DeepPrep.exe", "--oculta"]), self.nuevos)
        self.assertTrue((self.nuevos / "clave.txt").is_file())
        self.assertFalse(self.viejos.exists())

    def test_la_que_instala_la_actualizacion_usa_la_vieja(self):
        # La lanza la 1.0.x desde su descarga, que está dentro de la carpeta de datos vieja.
        datos_de_porofesor(self.viejos)
        with mock.patch.object(config, "RAIZ", self.viejos / "actualizacion" / "nueva" / "DeepPrep"):
            self.assertEqual(config.elegir_datos(self.entorno, ["Porofesor.exe", "--actualizar", "1", "x"]), self.viejos)
        self.assertEqual(config.elegir_datos(self.entorno, ["DeepPrep.exe", "--actualizar", "1", "x"]), self.viejos)
        self.assertEqual(config.elegir_datos(self.entorno, ["DeepPrep.exe", "--grabar"]), self.viejos)
        self.assertTrue((self.viejos / "clave.txt").is_file())
        self.assertFalse(self.nuevos.exists())

    def test_sin_porofesor_la_nueva(self):
        self.assertEqual(config.elegir_datos(self.entorno, ["DeepPrep.exe"]), self.nuevos)

    def test_variables_de_prueba(self):
        datos_de_porofesor(self.viejos)
        self.assertEqual(config.elegir_datos({**self.entorno, "DEEPPREP_DATOS": "C:/a"}, []), Path("C:/a"))
        self.assertEqual(config.elegir_datos({**self.entorno, "POROFESOR_DATOS": "C:/b"}, []), Path("C:/b"))
        self.assertEqual(config.elegir_datos({**self.entorno, "DEEPPREP_DATOS": "C:/a", "POROFESOR_DATOS": "C:/b"}, []), Path("C:/a"))
        self.assertTrue((self.viejos / "clave.txt").is_file())  # con carpeta propia no se muda nada
        with mock.patch.object(config, "CONGELADA", False):
            self.assertEqual(config.elegir_datos(self.entorno, []), self.programa)  # desde el código, la RAIZ


def acceso_de_mentira(acceso, carpeta):
    """Un .lnk que lleva a esa carpeta: la ruta va dentro en UTF-16, como la escribe Windows."""
    acceso.parent.mkdir(parents=True, exist_ok=True)
    acceso.write_bytes(b"L\0\0\0" + str(Path(carpeta) / "Porofesor.exe").encode("utf-16-le") + b"\0\0")


class ConInstalaciones(ConCarpetaTemporal):
    """Una Porofesor 1.0.2 instalada y la 2.0.0 descargada (zip puente), con los accesos directos de prueba."""

    def setUp(self):
        super().setUp()
        self.vieja = self.tmp / "Programs" / "Porofesor"
        self.nueva = self.tmp / "Programs" / "DeepPrep"
        (self.vieja / "_internal").mkdir(parents=True)
        (self.vieja / "Porofesor.exe").write_bytes(b"MZ 1.0.2")
        (self.vieja / "_internal" / "viejo.dll").write_bytes(b"dll")
        (self.vieja / "version.txt").write_text("1.0.2", encoding="utf-8")
        self.descarga = self.tmp / "datos" / "actualizacion" / "nueva" / "DeepPrep"
        self.carpeta_de_mentira(self.descarga, puente=True)
        self.escritorio, self.inicio = self.tmp / "Desktop", self.tmp / "Startup"
        acceso_de_mentira(self.escritorio / "Porofesor.lnk", self.vieja)
        acceso_de_mentira(self.inicio / "Porofesor.lnk", self.vieja)
        self.creados = []

        def crear(destino, objetivo, argumentos="", descripcion="Deep Prep"):
            self.creados.append((Path(destino), Path(objetivo), argumentos))
            Path(destino).write_bytes(b"L")

        self.popen = mock.MagicMock()
        self.cfg = {"siempre_en_marcha": True}
        self.parches = [
            mock.patch.object(act, "CARPETA_PROGRAMA", self.nueva),
            mock.patch.object(act, "CARPETA_PROGRAMA_VIEJA", self.vieja),
            mock.patch.object(act, "ESCRITORIO", self.escritorio / "Deep Prep.lnk"),
            mock.patch.object(act, "ESCRITORIO_VIEJO", self.escritorio / "Porofesor.lnk"),
            mock.patch.object(inicio_windows, "ACCESO", self.inicio / "Deep Prep.lnk"),
            mock.patch.object(inicio_windows, "ACCESO_VIEJO", self.inicio / "Porofesor.lnk"),
            # La 1.0.x lanza la copia Porofesor.exe del zip puente.
            mock.patch.object(act, "sys", types.SimpleNamespace(executable=str(self.descarga / "Porofesor.exe"))),
            mock.patch.object(act, "acceso_directo", crear),
            mock.patch.object(act.subprocess, "Popen", self.popen),
            mock.patch.object(config, "cargar", lambda: dict(self.cfg)),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in reversed(self.parches):
            p.stop()
        super().tearDown()

    @staticmethod
    def carpeta_de_mentira(carpeta, puente=False):
        """Lo que deja PyInstaller (una carpeta: el .exe y _internal al lado) y, en el zip puente, Porofesor.exe."""
        (carpeta / "_internal").mkdir(parents=True)
        (carpeta / "ffmpeg").mkdir()
        (carpeta / "DeepPrep.exe").write_bytes(b"MZ deep prep")
        (carpeta / "_internal" / "base_library.zip").write_bytes(b"zip")
        (carpeta / "ffmpeg" / "ffmpeg.exe").write_bytes(b"MZ ffmpeg")
        if puente:
            shutil.copyfile(carpeta / "DeepPrep.exe", carpeta / "Porofesor.exe")

    def lanzado(self):
        self.popen.assert_called_once()
        return self.popen.call_args.args[0], self.popen.call_args.kwargs.get("cwd")


class InstalacionDesdePorofesor(ConInstalaciones):
    def test_se_instala_en_la_carpeta_nueva(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(act.terminar_actualizacion("0", str(self.vieja), "--oculta"))
        self.assertEqual((self.nueva / "DeepPrep.exe").read_bytes(), b"MZ deep prep")
        self.assertTrue((self.nueva / "_internal" / "base_library.zip").is_file())
        self.assertTrue((self.nueva / "ffmpeg" / "ffmpeg.exe").is_file())
        self.assertEqual((self.nueva / "version.txt").read_text(encoding="utf-8"), __version__)
        self.assertFalse((self.nueva / "Porofesor.exe").exists())
        self.assertFalse(self.vieja.exists())  # el programa viejo, fuera
        self.assertEqual(self.lanzado(), ([str(self.nueva / "DeepPrep.exe"), "--oculta"], str(self.nueva)))

    def test_cambia_los_accesos_directos(self):
        with contextlib.redirect_stdout(io.StringIO()):
            act.terminar_actualizacion("0", str(self.vieja), "--oculta")
        self.assertFalse((self.escritorio / "Porofesor.lnk").exists())
        self.assertFalse((self.inicio / "Porofesor.lnk").exists())
        exe = self.nueva / "DeepPrep.exe"
        self.assertEqual(self.creados, [(self.escritorio / "Deep Prep.lnk", exe, ""), (self.inicio / "Deep Prep.lnk", exe, "--oculta")])

    def test_sin_siempre_en_marcha_no_arranca_con_windows(self):
        self.cfg["siempre_en_marcha"] = False
        with contextlib.redirect_stdout(io.StringIO()):
            act.terminar_actualizacion("0", str(self.vieja), "--oculta")
        self.assertEqual([c[0] for c in self.creados], [self.escritorio / "Deep Prep.lnk"])
        self.assertFalse((self.inicio / "Porofesor.lnk").exists())

    def test_deja_los_accesos_directos_que_no_son_de_la_instalada(self):
        # Quien usa Porofesor desde el código tiene su acceso de Inicio apuntando a su carpeta: ese no se toca.
        acceso_de_mentira(self.inicio / "Porofesor.lnk", self.tmp / "codigo" / "porofesor")
        with contextlib.redirect_stdout(io.StringIO()):
            act.terminar_actualizacion("0", str(self.vieja), "--oculta")
        self.assertTrue((self.inicio / "Porofesor.lnk").exists())
        self.assertFalse((self.escritorio / "Porofesor.lnk").exists())

    def test_no_borra_el_programa_viejo_si_aun_corre_algo(self):
        with mock.patch.object(act, "_en_uso", return_value=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(act.terminar_actualizacion("0", str(self.vieja), "--oculta"))
        self.assertTrue((self.vieja / "Porofesor.exe").is_file())
        self.assertTrue((self.nueva / "DeepPrep.exe").is_file())
        self.assertEqual(self.lanzado()[0][0], str(self.nueva / "DeepPrep.exe"))

    def test_si_no_se_puede_instalar_abre_la_de_antes(self):
        with mock.patch.object(act.shutil, "copytree", side_effect=OSError("disco lleno")), \
                mock.patch.object(act.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(act.terminar_actualizacion("0", str(self.vieja), "--oculta"))
        self.assertEqual(self.lanzado(), ([str(self.vieja / "Porofesor.exe"), "--oculta"], str(self.vieja)))
        self.assertTrue((self.vieja / "Porofesor.exe").is_file())
        self.assertTrue((self.escritorio / "Porofesor.lnk").exists())
        self.assertEqual(self.creados, [])

    def test_la_1_0_0_no_dice_el_modo(self):
        with mock.patch.object(act, "_segundos_encendido", return_value=0), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(act.terminar_actualizacion("0", str(self.vieja)))
        self.assertEqual(self.lanzado()[0], [str(self.nueva / "DeepPrep.exe"), "--oculta"])

    def test_una_actualizacion_normal_no_toca_lo_de_porofesor(self):
        self.carpeta_de_mentira(self.nueva)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(act.terminar_actualizacion("0", str(self.nueva), "--mostrar"))
        self.assertTrue((self.vieja / "Porofesor.exe").is_file())
        self.assertTrue((self.escritorio / "Porofesor.lnk").exists())
        self.assertEqual(self.creados, [])
        self.assertEqual(self.lanzado()[0], [str(self.nueva / "DeepPrep.exe")])

    def test_no_toca_carpetas_que_no_son_una_instalacion(self):
        codigo = self.tmp / "codigo" / "Porofesor"
        (codigo / ".git").mkdir(parents=True)
        (codigo / "Porofesor.exe").write_bytes(b"MZ")
        for carpeta in (codigo, self.tmp / "otra" / "Porofesor"):
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / "notas.txt").write_text("mío", encoding="utf-8")
            acceso_de_mentira(self.escritorio / "Porofesor.lnk", carpeta)
            with contextlib.redirect_stdout(io.StringIO()):
                act.quitar_restos_de_porofesor(carpeta)
            self.assertTrue((carpeta / "notas.txt").is_file())
            self.assertTrue((self.escritorio / "Porofesor.lnk").exists())  # ni lo que lleva a ella

    def test_quita_los_accesos_que_llevan_a_un_programa_ya_borrado(self):
        shutil.rmtree(self.vieja)
        with contextlib.redirect_stdout(io.StringIO()):
            act.quitar_restos_de_porofesor()
        self.assertFalse((self.escritorio / "Porofesor.lnk").exists())
        self.assertFalse((self.inicio / "Porofesor.lnk").exists())


class ProgramaEnMarcha(unittest.TestCase):
    def test_sabe_si_corre_algo_desde_la_carpeta(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            exe = Path(d) / "ping.exe"
            shutil.copyfile(Path(shutil.which("ping") or "C:/Windows/System32/PING.EXE"), exe)
            self.assertFalse(act._en_uso(d))
            p = subprocess.Popen([str(exe), "-n", "3", "127.0.0.1"], stdout=subprocess.DEVNULL, creationflags=act.SIN_VENTANA)
            try:
                time.sleep(0.3)
                self.assertTrue(act._en_uso(d))
            finally:
                p.kill()
                p.wait()


def cargar_publicar():
    spec = importlib.util.spec_from_file_location("publicar", RAIZ / "herramientas" / "publicar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def actualizador_de_la_1_0_x(rel, bajar, carpeta):
    """Lo que hace Porofesor 1.0.2 con su releases/latest (Actualizador.comprobar y aplicar de
    5ac0b3e:porofesor/actualizador.py), copiado tal cual: devuelve el .exe que lanzaría con --actualizar."""
    activos = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    zip_nombre = next((n for n in activos if n.endswith(".zip")), None)
    if not zip_nombre or f"{zip_nombre}.sha256" not in activos:
        raise RuntimeError("no trae el zip con su huella")
    huella = bajar(activos[f"{zip_nombre}.sha256"]).decode().split()[0].lower()
    datos = bajar(activos[zip_nombre])
    if hashlib.sha256(datos).hexdigest() != huella:
        raise RuntimeError("no coincide con su huella")
    zip_ruta = carpeta / zip_nombre
    zip_ruta.write_bytes(datos)
    destino = carpeta / "nueva"
    with zipfile.ZipFile(zip_ruta) as z:
        z.extractall(destino)
    zip_ruta.unlink(missing_ok=True)
    exe = next(destino.rglob("Porofesor.exe"), None)
    if not exe:
        raise RuntimeError("no trae Porofesor.exe")
    return exe.parent / "Porofesor.exe"


def version_publicada(zip_ruta, tag="v2.0.0"):
    """La versión como la devuelve GitHub (releases/latest) y una descarga de mentira de sus archivos."""
    sha = Path(f"{zip_ruta}.sha256")
    rel = {"tag_name": tag, "body": NOTAS, "assets": [{"name": zip_ruta.name, "browser_download_url": str(zip_ruta)},
                                                      {"name": sha.name, "browser_download_url": str(sha)}]}
    return rel, lambda url, binario=True: Path(url).read_bytes() if binario else rel


class ZipPuente(ConInstalaciones):
    def setUp(self):
        super().setUp()
        self.publicar = cargar_publicar()
        self.dist = self.tmp / "dist" / "DeepPrep"
        self.carpeta_de_mentira(self.dist)
        (self.dist / "LEEME.txt").write_text("Deep Prep", encoding="utf-8")

    def comprimir(self, puente):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.publicar.comprimir("2.0.0", puente=puente, dist=self.dist, carpeta=self.tmp / ("puente" if puente else "zip"))

    def test_la_1_0_x_encuentra_porofesor_exe_en_el_zip_puente(self):
        rel, bajar = version_publicada(self.comprimir(puente=True))
        (self.tmp / "bajada").mkdir()
        exe = actualizador_de_la_1_0_x(rel, bajar, self.tmp / "bajada")
        self.assertEqual(exe.name, "Porofesor.exe")
        self.assertEqual(exe.read_bytes(), (self.dist / "DeepPrep.exe").read_bytes())  # copia exacta
        self.assertTrue((exe.parent / "_internal" / "base_library.zip").is_file())  # con _internal al lado
        self.assertTrue((exe.parent / "DeepPrep.exe").is_file())

    def test_sin_puente_la_1_0_x_no_podria_actualizarse(self):
        rel, bajar = version_publicada(self.comprimir(puente=False))
        (self.tmp / "bajada").mkdir()
        with self.assertRaisesRegex(RuntimeError, "Porofesor.exe"):
            actualizador_de_la_1_0_x(rel, bajar, self.tmp / "bajada")

    def test_deep_prep_acepta_los_dos_zips(self):
        for puente in (False, True):
            descargas = self.tmp / f"descargas{puente}"
            descargas.mkdir()
            rel, bajar = version_publicada(self.comprimir(puente), tag="v9.9.9")
            with mock.patch.object(act, "CARPETA_DESCARGA", descargas), mock.patch.object(act, "NOVEDADES", descargas / "novedades.json"), \
                    mock.patch.object(act, "_get", lambda url, binario=False: bajar(url, binario)), contextlib.redirect_stdout(io.StringIO()):
                a = act.Actualizador(app=None)
                self.assertTrue(a.comprobar())
            self.assertTrue((a._carpeta_nueva / "DeepPrep.exe").is_file())

    def test_del_zip_puente_a_deep_prep_instalada(self):
        rel, bajar = version_publicada(self.comprimir(puente=True))
        (self.tmp / "bajada").mkdir()
        exe = actualizador_de_la_1_0_x(rel, bajar, self.tmp / "bajada")
        # La 1.0.x lanza: Porofesor.exe --actualizar PID ...\Programs\Porofesor --oculta
        with mock.patch.object(act, "sys", types.SimpleNamespace(executable=str(exe))), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(act.terminar_actualizacion("0", str(self.vieja), "--oculta"))
        self.assertEqual(sorted(p.name for p in self.nueva.iterdir()), ["DeepPrep.exe", "LEEME.txt", "_internal", "ffmpeg", "version.txt"])
        self.assertFalse(self.vieja.exists())
        self.assertEqual(self.lanzado()[0], [str(self.nueva / "DeepPrep.exe"), "--oculta"])


if __name__ == "__main__":
    unittest.main()
