"""Instalación y actualizaciones de la app empaquetada (la que se pasa a los amigos).

- Instalar: la primera vez que se abre el .exe desde donde se haya descomprimido, se copia a
  %LOCALAPPDATA%\\Programs\\DeepPrep, deja un acceso directo en el escritorio y arranca desde ahí.
- Actualizar: cada 6 horas mira la última versión publicada en GitHub. Si hay una nueva, la descarga,
  comprueba su huella (sha256) y la instala cuando no estorba: sin partida, sin selección, sin grabación
  y sin revisión pendiente. Los datos del usuario están en otra carpeta y no se tocan.
- De Porofesor a Deep Prep: hasta la 1.0.2 la app se llamaba Porofesor. Esas versiones se actualizan desde
  su repositorio de descargas, donde va también la 2.0.0 (zip puente, ver herramientas/publicar.py), y piden
  instalarla en %LOCALAPPDATA%\\Programs\\Porofesor. La 2.0.0 se instala en la carpeta nueva, cambia los
  accesos directos y borra el programa viejo; los datos los muda config.py al abrirse la copia instalada.

Desde el código (la copia de Samuel) no hace nada de esto.
"""
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from . import __version__, config, inicio_windows

REPO = "Samuelmartinezduran/deep-prep"
EXE = "DeepPrep.exe"
CARPETA_PROGRAMA = config.PROGRAMA
CARPETA_DESCARGA = config.DATOS / "actualizacion"
ESCRITORIO = Path(os.environ.get("DEEPPREP_ESCRITORIO") or os.environ.get("POROFESOR_ESCRITORIO")
                  or Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop" / "Deep Prep.lnk")
# Lo que instalaba Porofesor (hasta la 1.0.2). Va al lado de lo nuevo, así que con las variables de prueba
# (DEEPPREP_PROGRAMA, DEEPPREP_ESCRITORIO) también cae en carpetas de prueba.
EXE_VIEJO = "Porofesor.exe"  # solo viene en el zip puente, para que lo encuentren las 1.0.x; no se instala
CARPETA_PROGRAMA_VIEJA = CARPETA_PROGRAMA.with_name("Porofesor")
ESCRITORIO_VIEJO = ESCRITORIO.with_name("Porofesor.lnk")
CADA = 6 * 3600
# Una actualización pedida por la 1.0.0 o la 1.0.1 no dice si reabrir la app a la vista o escondida. Con el PC
# recién encendido es el arranque con Windows (escondida); si no, lo normal es que la persona acabe de abrirla
# y esté mirando: se reabre a la vista, para que no parezca que se ha cerrado sola.
ARRANQUE_RECIENTE_S = 10 * 60
# Sin ventana propia (panel en el navegador), alguien lo está mirando si lo ha pedido hace menos de esto.
MIRANDO_S = 120
# Notas de la versión que se acaba de descargar: la versión nueva las enseña una vez al abrirse.
NOVEDADES = config.DATOS / "novedades.json"
# Última versión cuyas novedades se han visto. Si no está, quien viene de una versión que no la guardaba.
VISTA = config.DATOS / "version_vista.txt"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DESLIGADO = SIN_VENTANA | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def version(texto):
    """'v1.2.10' -> (1, 2, 10) para comparar versiones."""
    try:
        return tuple(int(x) for x in str(texto).lstrip("vV").split("."))
    except ValueError:
        return (0,)


def _get(url, binario=False):
    pet = urllib.request.Request(url, headers={"User-Agent": "deep-prep", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(pet, timeout=60) as r:
        datos = r.read()
    return datos if binario else json.loads(datos)


def acceso_directo(destino, objetivo, argumentos="", descripcion="Deep Prep"):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:DESTINO); $s.TargetPath=$env:OBJETIVO;"
          "$s.Arguments=$env:ARGS; $s.WorkingDirectory=$env:CARPETA; $s.Description=$env:DESC; $s.Save()")
    entorno = dict(os.environ, DESTINO=str(destino), OBJETIVO=str(objetivo), ARGS=argumentos, CARPETA=str(Path(objetivo).parent), DESC=descripcion)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=entorno, capture_output=True, creationflags=SIN_VENTANA)


def _segundos_encendido():
    try:
        k32 = ctypes.windll.kernel32
        k32.GetTickCount64.restype = ctypes.c_ulonglong
        return k32.GetTickCount64() / 1000
    except (AttributeError, OSError):
        return 0


def _marcar_version(carpeta):
    try:
        (Path(carpeta) / "version.txt").write_text(__version__, encoding="utf-8")
    except OSError:
        pass


def _version_instalada():
    """La versión instalada: la de la copia en marcha si la hay; si no, la que dejó apuntada al instalarse."""
    puerto = config.cargar().get("puerto", 5151)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/ajustes", timeout=5) as r:
            return json.loads(r.read())["version"]["version"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        return (CARPETA_PROGRAMA / "version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _abrir_la_instalada():
    """Enseña la ventana de la copia instalada (o la arranca si no está en marcha)."""
    puerto = config.cargar().get("puerto", 5151)
    url = f"http://127.0.0.1:{puerto}/"
    pet = urllib.request.Request(url + "api/mostrar", data=b"{}", headers={"Origin": url.rstrip("/"), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pet, timeout=5) as r:
            if json.loads(r.read()).get("ok"):
                return
    except (OSError, ValueError):
        pass
    exe = CARPETA_PROGRAMA / EXE
    if exe.is_file():
        subprocess.Popen([str(exe)], cwd=str(CARPETA_PROGRAMA), creationflags=DESLIGADO)


# --- de Porofesor a Deep Prep -------------------------------------------------------------------------------
def _en_uso(carpeta):
    """¿Corre algún programa de esa carpeta? Windows no deja abrir para escribir un .exe que está en marcha."""
    for exe in Path(carpeta).rglob("*.exe"):
        try:
            with open(exe, "r+b"):
                pass
        except PermissionError:
            return True
        except OSError:
            pass
    return False


def _apunta_a(acceso, carpeta):
    """¿El acceso directo (.lnk) lleva a algo de esa carpeta? La ruta va escrita dentro, en ANSI y en UTF-16."""
    try:
        datos = acceso.read_bytes().lower()
    except OSError:
        return False
    ruta = str(carpeta)
    return any(ruta.encode(codigo, "ignore").lower() in datos for codigo in ("mbcs", "utf-16-le"))


def quitar_restos_de_porofesor(carpeta=None):
    """Quita lo que dejó instalado Porofesor (1.0.x): sus accesos directos y la carpeta del programa.

    Solo los accesos directos que llevan a esa carpeta (los de quien la usa desde el código apuntan a otro sitio)
    y solo la carpeta si es una instalación y no corre nada desde ella. Lo que no se pueda quitar se apunta en el
    registro y se queda: nunca estropea la actualización. Se reintenta en cada arranque mientras quede algo.
    """
    carpeta = Path(carpeta or CARPETA_PROGRAMA_VIEJA)
    try:
        if carpeta.resolve() == CARPETA_PROGRAMA.resolve():
            return
        instalada = ((carpeta / EXE_VIEJO).is_file() or (carpeta / "_internal").is_dir()) and not (carpeta / ".git").exists()
        if carpeta.exists() and not instalada:
            return  # no es una Porofesor instalada (p. ej. su código): ni la carpeta ni lo que lleva a ella
        for acceso in (ESCRITORIO_VIEJO, inicio_windows.ACCESO_VIEJO):
            if acceso.is_file() and _apunta_a(acceso, carpeta):
                acceso.unlink()
                print(f"Quitado el acceso directo de Porofesor {acceso}")
        if not instalada:
            return
        if _en_uso(carpeta):
            print(f"No borro {carpeta}: aún corre algo desde ahí; se intenta en el próximo arranque")
            return
        for intento in range(5):  # el antivirus puede tener algo abierto un momento
            try:
                shutil.rmtree(carpeta)
                print(f"Borrado el programa de Porofesor ({carpeta})")
                return
            except OSError as e:
                error = e
                time.sleep(1)
        print(f"No se pudo borrar {carpeta}: {error!r}; se queda ahí")
    except Exception as e:  # noqa: BLE001  la limpieza nunca puede tumbar la actualización
        print(f"No se pudo quitar lo que dejó Porofesor ({carpeta}): {e!r}")


def _pasar_de_porofesor(exe, vieja):
    """Deep Prep recién instalada encima de una Porofesor (1.0.x): accesos directos nuevos y fuera los viejos."""
    quitar_restos_de_porofesor(vieja)
    try:
        acceso_directo(ESCRITORIO, exe)
        # El arranque con Windows sigue como lo tenía: lo decide "siempre en marcha" de su configuración (la de
        # Porofesor, que es la que ve este proceso; los datos se mudan al abrirse la copia instalada).
        if config.cargar().get("siempre_en_marcha"):
            acceso_directo(inicio_windows.ACCESO, exe, "--oculta", "Deep Prep (en segundo plano)")
    except Exception as e:  # noqa: BLE001
        print(f"No se pudieron crear los accesos directos de Deep Prep: {e!r}")


# --- instalación ------------------------------------------------------------------------------------------
def instalar_si_hace_falta():
    """En la app empaquetada abierta desde fuera de su carpeta: se instala y arranca la copia instalada.

    Devuelve True si esta copia tiene que cerrarse (ya arrancó la instalada).
    """
    if not config.CONGELADA:
        return False
    aqui = Path(sys.executable).parent.resolve()
    if aqui == CARPETA_PROGRAMA.resolve():
        return False
    # Abrir el .exe de un zip viejo no puede pisar una versión más nueva ya instalada (se actualizó sola).
    instalada = _version_instalada()
    if version(instalada) > version(__version__):
        print(f"Ya está instalada la {instalada}, más nueva que esta {__version__}: abro esa")
        _abrir_la_instalada()
        return True
    _cerrar_la_instalada()
    if CARPETA_PROGRAMA.exists():
        shutil.rmtree(CARPETA_PROGRAMA, ignore_errors=True)
    shutil.copytree(aqui, CARPETA_PROGRAMA, dirs_exist_ok=True, ignore=shutil.ignore_patterns(EXE_VIEJO))
    _marcar_version(CARPETA_PROGRAMA)
    try:
        VISTA.parent.mkdir(parents=True, exist_ok=True)
        VISTA.write_text(__version__, encoding="utf-8")  # instalación nueva: no hay novedades que contar
    except OSError:
        pass
    exe = CARPETA_PROGRAMA / EXE
    acceso_directo(ESCRITORIO, exe)
    # Descargada a mano encima de una Porofesor (ya cerrada arriba): fuera sus accesos directos y su programa.
    quitar_restos_de_porofesor()
    subprocess.Popen([str(exe)], cwd=str(CARPETA_PROGRAMA), creationflags=DESLIGADO)
    return True


def _cerrar_la_instalada(puerto=None):
    """Si ya hay una Deep Prep (o una Porofesor) en marcha, se le pide que se cierre antes de reinstalar."""
    puerto = puerto or config.cargar().get("puerto", 5151)
    url = f"http://127.0.0.1:{puerto}/"
    pet = urllib.request.Request(url + "api/salir", data=b"{}", headers={"Origin": url.rstrip("/"), "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(pet, timeout=5).read()
    except OSError:
        return
    for _ in range(30):  # hasta que suelte el puerto
        time.sleep(0.5)
        try:
            urllib.request.urlopen(url + "api/estado", timeout=1).read()
        except OSError:
            return


def terminar_actualizacion(pid, destino, modo=None):
    """Lo hace la versión nueva ("--actualizar PID DESTINO [--oculta|--mostrar]"): espera a que la vieja se cierre,
    se copia encima y la abre. Sin modo (lo piden la 1.0.0 y la 1.0.1), se decide por el arranque del PC.

    Si la pide una Porofesor (1.0.x), DESTINO es su carpeta (...\\Programs\\Porofesor): la versión nueva se instala
    en la de Deep Prep, sin Porofesor.exe, pone los accesos directos nuevos y quita los viejos y el programa viejo."""
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
    if h:
        k32.WaitForSingleObject(h, 120_000)
        k32.CloseHandle(h)
    origen = Path(sys.executable).parent
    destino = Path(destino)
    vieja = None
    if destino.name.lower() == "porofesor" and destino.resolve() != CARPETA_PROGRAMA.resolve():
        vieja, destino = destino, CARPETA_PROGRAMA
    # Se copia encima (sin borrar antes): si algo falla a medias, sigue habiendo una app que abrir.
    copiada, error = False, None
    for intento in range(20):  # el antivirus o el propio Windows pueden tener algo abierto un momento
        try:
            shutil.copytree(origen, destino, dirs_exist_ok=True, ignore=shutil.ignore_patterns(EXE_VIEJO))
            copiada = True
            break
        except OSError as e:
            error = e
            time.sleep(1.5)
    if copiada:
        _marcar_version(destino)
        if vieja:
            _pasar_de_porofesor(destino / EXE, vieja)
    else:
        print(f"No se pudo instalar la {__version__} en {destino}: {error!r}. Se abre la que había.")
        if vieja:  # la Porofesor de antes sigue entera: se abre esa, que ya lo volverá a intentar
            destino = vieja
    if modo not in ("--oculta", "--mostrar"):
        modo = "--oculta" if _segundos_encendido() < ARRANQUE_RECIENTE_S else "--mostrar"
    exe = destino / (EXE_VIEJO if destino == vieja else EXE)
    if not exe.is_file():
        print(f"No está {exe}: hay que volver a descargar la app")
        return False
    subprocess.Popen([str(exe)] + (["--oculta"] if modo == "--oculta" else []), cwd=str(destino), creationflags=DESLIGADO)
    print(f"Versión {__version__} instalada; se abre {'escondida' if modo == '--oculta' else 'a la vista'}")
    return copiada


# --- actualizaciones ----------------------------------------------------------------------------------------
class Actualizador:
    def __init__(self, app, repo=REPO):
        self.app = app
        self.repo = repo
        self.estado = {"version": __version__, "nueva": None, "lista": False, "error": ""}
        self._carpeta_nueva = None

    def arrancar(self):
        if config.CONGELADA:
            # Restos de una actualización ya instalada.
            if not Path(sys.executable).resolve().is_relative_to(CARPETA_DESCARGA.resolve()):
                shutil.rmtree(CARPETA_DESCARGA / "nueva", ignore_errors=True)
            # Lo de Porofesor que no se pudo quitar al pasar a Deep Prep (p. ej. aún corría algo desde ahí).
            if CARPETA_PROGRAMA_VIEJA.exists() or ESCRITORIO_VIEJO.exists() or inicio_windows.ACCESO_VIEJO.exists():
                threading.Thread(target=quitar_restos_de_porofesor, name="restos", daemon=True).start()
            threading.Thread(target=self._bucle, name="actualizador", daemon=True).start()
            if self._faltan_novedades():
                threading.Thread(target=self._bajar_novedades, name="novedades", daemon=True).start()

    def _faltan_novedades(self):
        try:
            vista = VISTA.read_text(encoding="utf-8").strip()
        except OSError:
            vista = ""
        return vista != __version__ and not self.novedades()

    def _bajar_novedades(self):
        """Recién actualizada desde una versión que no bajó las notas (la 1.0.0): se piden a GitHub."""
        try:
            rel = _get(f"https://api.github.com/repos/{self.repo}/releases/tags/v{__version__}")
            NOVEDADES.write_text(json.dumps({"version": __version__, "notas": rel.get("body") or ""}, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: BLE001  sin red: se quedan sin novedades esta vez
            print(f"No se pudieron leer las novedades de {__version__}: {e}")

    def _bucle(self):
        ultima = 0.0
        while True:
            try:
                if time.time() - ultima > CADA:
                    ultima = time.time()
                    self.comprobar()
                if self.estado["lista"] and self.puede_instalar():
                    self.aplicar()
                    return
            except Exception as e:  # noqa: BLE001  sin red o GitHub caído: se reintenta más tarde
                self.estado["error"] = str(e)[:200]
            time.sleep(60)

    def comprobar(self):
        """Mira la última versión publicada; si es más nueva, la descarga y la deja lista."""
        rel = _get(f"https://api.github.com/repos/{self.repo}/releases/latest")
        nueva = rel.get("tag_name", "")
        if version(nueva) <= version(__version__):
            return False
        activos = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        zip_nombre = next((n for n in activos if n.endswith(".zip")), None)
        if not zip_nombre or f"{zip_nombre}.sha256" not in activos:
            raise RuntimeError(f"La versión {nueva} no trae el zip con su huella")
        huella = _get(activos[f"{zip_nombre}.sha256"], binario=True).decode().split()[0].lower()
        CARPETA_DESCARGA.mkdir(parents=True, exist_ok=True)
        zip_ruta = CARPETA_DESCARGA / zip_nombre
        datos = _get(activos[zip_nombre], binario=True)
        if hashlib.sha256(datos).hexdigest() != huella:
            raise RuntimeError(f"La descarga de {nueva} no coincide con su huella; no se instala")
        zip_ruta.write_bytes(datos)
        destino = CARPETA_DESCARGA / "nueva"
        shutil.rmtree(destino, ignore_errors=True)
        with zipfile.ZipFile(zip_ruta) as z:
            z.extractall(destino)
        zip_ruta.unlink(missing_ok=True)
        exe = next(destino.rglob(EXE), None)
        if not exe:
            raise RuntimeError(f"La versión {nueva} no trae {EXE}")
        self._carpeta_nueva = exe.parent
        try:
            NOVEDADES.write_text(json.dumps({"version": nueva.lstrip("vV"), "notas": rel.get("body") or ""}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        self.estado.update(nueva=nueva.lstrip("vV"), lista=True, error="")
        print(f"Versión {nueva} descargada; se instala en cuanto no estorbe")
        return True

    def novedades(self):
        """Lo nuevo de esta versión si se acaba de instalar y aún no se ha visto; si no, None."""
        try:
            n = json.loads(NOVEDADES.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return n if n.get("version") == __version__ else None

    def novedades_vistas(self):
        NOVEDADES.unlink(missing_ok=True)
        try:
            VISTA.write_text(__version__, encoding="utf-8")
        except OSError:
            pass
        return {"ok": True}

    def puede_instalar(self):
        """Sin partida a la vista, sin grabación, sin revisiones pendientes y sin nadie mirando la ventana:
        instalar cierra la app, y cerrarla delante de alguien parece que se ha roto."""
        app = self.app
        grabando = bool(app.grabador and app.grabador.activa())
        visible = getattr(app, "ventana_visible", None)
        mirando = visible() if visible else time.time() - getattr(app, "ultima_consulta", 0) < MIRANDO_S
        return (app.fase in (None, "None", "Lobby", "EndOfGame") and app.modo == "previa" and not grabando
                and not app.revisando and not mirando)

    def aplicar(self):
        """Arranca la versión nueva (desde la descarga) para que espere a que esta se cierre y se instale ella."""
        nueva = self._carpeta_nueva / EXE
        subprocess.Popen([str(nueva), "--actualizar", str(os.getpid()), str(CARPETA_PROGRAMA), "--oculta"],
                         cwd=str(self._carpeta_nueva), creationflags=DESLIGADO)
        print(f"Instalando la versión {self.estado['nueva']}; la app se reabre sola")
        if self.app.al_salir:
            self.app.al_salir()
        else:
            os._exit(0)
