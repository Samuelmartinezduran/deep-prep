"""Graba la pantalla de cada partida en la Grieta (ffmpeg, trozos de 5 minutos) en Vídeos\\LoL-coach.

La grabación va en un proceso aparte ("deepprep --grabar"): espera a que se abra el juego, graba la
pantalla donde está y para sola al acabar la partida, aunque la app se reinicie o se cierre por medio.
La app solo lo lanza, mira el registro para saber en qué carpeta graba y avisa si el vídeo deja de crecer.

Codificador: "auto" usa el de la gráfica si hay (NVIDIA, AMD o Intel) y si no el procesador; "cpu"
fuerza el procesador. Las grabaciones más viejas se borran solas al pasar de grabacion_max_gb (0 = nunca).
"""
import ctypes
import ctypes.wintypes as wt
import datetime
import msvcrt
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config

RUTA_LOG = config.DATOS / "grabacion.log"
RUTA_CERROJO = config.DATOS / "grabacion.lock"
GRIETA = 11
# Si el vídeo lleva este tiempo sin crecer, algo va mal y el panel lo avisa.
SEGUNDOS_SIN_CRECER = 20
CLASE_JUEGO = "RiotWindowClass"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Ajustes de cada codificador, de mejor a peor opción. El de procesador es el del script de coaching.
CODIFICADORES = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p3", "-rc", "vbr", "-cq", "26", "-b:v", "0", "-pix_fmt", "yuv420p"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26", "-pix_fmt", "yuv420p"],
    "h264_qsv": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "26", "-pix_fmt", "nv12"],
}
CPU = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p"]


# --- lo que usa la app ------------------------------------------------------------------------------
class Grabador:
    def __init__(self, cfg):
        self.cfg = cfg
        self._proceso = None
        self._lock = threading.Lock()
        self._medida = (0.0, -1)  # (cuándo, bytes) de la última vez que se midió el vídeo
        self._crecio = 0.0

    def activa(self):
        return (self._proceso is not None and self._proceso.poll() is None) or _cerrojo_ocupado()

    def armar(self, extra=()):
        """Deja un grabador esperando a la partida. No bloquea."""
        threading.Thread(target=self._armar, name="grabador", daemon=True).start()

    def _armar(self):
        with self._lock:
            if self.activa():
                print("No lanzo otro grabador: ya hay uno en marcha")
                return
            if not buscar_ffmpeg():
                print("No se graba: no encuentro ffmpeg")
                return
            if getattr(sys, "frozen", False):
                orden = [sys.executable, "--grabar"]
            else:
                orden = [sys.executable, "-X", "utf8", "-m", "deepprep", "--grabar"]
            try:
                self._proceso = subprocess.Popen(
                    orden, cwd=str(config.RAIZ), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=SIN_VENTANA | subprocess.CREATE_NEW_PROCESS_GROUP)
            except OSError as e:
                print(f"No se pudo lanzar el grabador: {e}")
                return
            self._medida = (0.0, -1)
            self._crecio = time.time()
            print("Grabador lanzado")

    def carpeta_reciente(self, horas=3):
        """Carpeta de la última grabación según el registro, si es de las últimas horas."""
        carpeta = _carpeta_del_registro()
        if not carpeta or not carpeta.is_dir() or time.time() - carpeta.stat().st_mtime > horas * 3600:
            return None
        return carpeta

    def estado(self):
        """None si no hay grabación; si la hay, la carpeta (vacía mientras espera al juego) y si se ha parado."""
        if not self.activa():
            return None
        carpeta = _carpeta_del_registro(solo_en_curso=True)
        if not carpeta:
            return {"carpeta": "", "parada": False}
        ahora = time.time()
        if ahora - self._medida[0] >= 5:
            total = _bytes_de(carpeta)
            if total > self._medida[1]:
                self._crecio = ahora
            self._medida = (ahora, total)
        return {"carpeta": str(carpeta), "parada": ahora - self._crecio > SEGUNDOS_SIN_CRECER}


def _carpeta_del_registro(solo_en_curso=False):
    try:
        texto = RUTA_LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"GRABANDO en (.+)", texto)
    if not m or (solo_en_curso and "TERMINADO" in texto):
        return None
    return Path(m.group(1).strip())


def _cerrojo_ocupado():
    """El proceso de grabación tiene cogido el cerrojo mientras vive."""
    try:
        with open(RUTA_CERROJO, "a") as f:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            return False
    except OSError:
        return False


def _bytes_de(carpeta):
    # El tamaño que da el listado de la carpeta va atrasado en el trozo que se está escribiendo;
    # hay que abrir cada archivo para saber cuánto ocupa de verdad.
    total = 0
    for f in Path(carpeta).glob("*.mkv"):
        try:
            with open(f, "rb") as a:
                total += a.seek(0, 2)
        except OSError:
            pass
    return total


# --- piezas del proceso de grabación -------------------------------------------------------------------
def buscar_ffmpeg():
    """El ffmpeg que va con la app empaquetada; si no, el instalado con winget o el del PATH."""
    candidatos = [config.RAIZ / "ffmpeg" / "ffmpeg.exe"]
    if getattr(sys, "frozen", False):
        candidatos.insert(0, Path(sys.executable).parent / "ffmpeg" / "ffmpeg.exe")
    paquetes = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    candidatos += sorted(paquetes.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))
    for c in candidatos:
        if c.is_file():
            return str(c)
    return shutil.which("ffmpeg")


def carpeta_videos():
    """Vídeos del usuario (aunque esté movida a OneDrive u otro disco)."""
    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    videos = GUID(0x18989B1D, 0x99B5, 0x455B, (ctypes.c_ubyte * 8)(0x84, 0x1C, 0xAB, 0x7C, 0x74, 0xE4, 0xDD, 0xFC))
    ruta = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(videos), 0, None, ctypes.byref(ruta)) == 0:
            try:
                return Path(ruta.value)
            finally:
                ctypes.windll.ole32.CoTaskMemFree(ruta)
    except (OSError, AttributeError):
        pass
    return Path.home() / "Videos"


def ventana_juego():
    return ctypes.windll.user32.FindWindowW(CLASE_JUEGO, None)


def salida_del_juego():
    """Número de pantalla (salida DXGI de la gráfica principal) en la que está el juego; 0 si no se sabe.

    ffmpeg (ddagrab) numera las pantallas así, que no siempre coincide con el orden de Windows.
    """
    hwnd = ventana_juego()
    if not hwnd:
        return 0
    monitor = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    class DESC(ctypes.Structure):
        _fields_ = [("nombre", ctypes.c_wchar * 32), ("rect", wt.RECT), ("unida", wt.BOOL), ("giro", ctypes.c_int), ("monitor", wt.HMONITOR)]

    def metodo(obj, indice, *tipos):
        tabla = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *tipos)(tabla[indice])

    def soltar(obj):
        if obj:
            metodo(obj, 2)(obj)

    iid = GUID(0x770AAE78, 0xF26F, 0x4DBA, (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87))  # IDXGIFactory1
    fabrica, adaptador = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        if ctypes.windll.dxgi.CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(fabrica)) != 0:
            return 0
        if metodo(fabrica, 12, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(fabrica, 0, ctypes.byref(adaptador)) != 0:  # EnumAdapters1
            return 0
        for i in range(8):
            salida = ctypes.c_void_p()
            if metodo(adaptador, 7, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(adaptador, i, ctypes.byref(salida)) != 0:  # EnumOutputs
                break
            desc = DESC()
            metodo(salida, 7, ctypes.POINTER(DESC))(salida, ctypes.byref(desc))  # GetDesc
            soltar(salida)
            if desc.monitor == monitor:
                return i
    except OSError:
        return 0
    finally:
        soltar(adaptador)
        soltar(fabrica)
    return 0


def elegir_codificador(ffmpeg, modo):
    """(nombre, argumentos) del codificador: el de la gráfica que funcione o, si no, el procesador."""
    if modo == "cpu":
        return "procesador", CPU
    for nombre, args in CODIFICADORES.items():
        prueba = [ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30", "-frames:v", "5", *args, "-f", "null", "-"]
        try:
            if subprocess.run(prueba, capture_output=True, timeout=20, creationflags=SIN_VENTANA).returncode == 0:
                return nombre, args
        except (OSError, subprocess.SubprocessError):
            pass
    return "procesador", CPU


def limpiar(base, max_gb, actual=None):
    """Borra las partidas grabadas más viejas hasta que todas juntas ocupen menos de max_gb."""
    if not max_gb or max_gb <= 0:
        return []
    carpetas = sorted((c for c in base.glob("*_partida*") if c.is_dir() and c != actual), key=lambda c: c.stat().st_mtime)
    tam = {c: sum(f.stat().st_size for f in c.rglob("*") if f.is_file()) for c in carpetas}
    total = sum(tam.values()) + (sum(f.stat().st_size for f in actual.rglob("*") if f.is_file()) if actual and actual.is_dir() else 0)
    borradas = []
    for c in carpetas:
        if total <= max_gb * 1024**3:
            break
        shutil.rmtree(c, ignore_errors=True)
        total -= tam[c]
        borradas.append(c.name)
    return borradas


# --- el proceso de grabación ("deepprep --grabar") -------------------------------------------------------
def grabar(cfg, espera_min=5, max_min=100, prueba_seg=0):
    """Espera a la partida, la graba y para al acabar. Escribe lo que hace en grabacion.log.

    prueba_seg: graba ese rato sin esperar al juego (para comprobar que funciona).
    """
    cerrojo = open(RUTA_CERROJO, "a")
    try:
        msvcrt.locking(cerrojo.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return  # ya hay otro grabando
    with open(RUTA_LOG, "w", encoding="utf-8", buffering=1) as log:
        ffmpeg = buscar_ffmpeg()
        if not ffmpeg:
            log.write("No encuentro ffmpeg; no se graba.\n")
            return
        inicio = time.time()
        while not prueba_seg and not ventana_juego():
            if time.time() - inicio > espera_min * 60:
                log.write(f"No ha empezado ninguna partida en {espera_min} min; no se ha grabado nada.\n")
                return
            time.sleep(2)

        base = carpeta_videos() / "LoL-coach"
        base.mkdir(parents=True, exist_ok=True)
        hoy = datetime.date.today().isoformat()
        n = 1
        while (base / f"{hoy}_partida{n}").exists():
            n += 1
        carpeta = base / (f"{hoy}_prueba" if prueba_seg else f"{hoy}_partida{n}")
        carpeta.mkdir(exist_ok=True)
        stop = base / "STOP"
        stop.unlink(missing_ok=True)
        nombre, args = elegir_codificador(ffmpeg, cfg.get("grabacion_codificador", "auto"))
        salida = salida_del_juego()
        log.write(f"GRABANDO en {carpeta}\n")
        log.write(f"Pantalla {salida}, codificador: {nombre}\n")

        empezo = time.time()

        def seguir():
            if prueba_seg:
                return time.time() - empezo < prueba_seg
            return ventana_juego() and not stop.exists() and time.time() - empezo < max_min * 60

        # ffmpeg se corta si cambia la resolución: se relanza mientras dure la partida (cada arranque, otra serie).
        for arranque in range(1, 200):
            if not seguir():
                break
            orden = [ffmpeg, "-hide_banner", "-v", "error", "-y", "-f", "lavfi",
                     "-i", f"ddagrab=output_idx={salida}:framerate=30,hwdownload,format=bgra", "-t", "6000", *args,
                     "-g", "60", "-f", "segment", "-segment_time", "300", "-reset_timestamps", "1",
                     str(carpeta / f"r{arranque:02d}_seg_%03d.mkv")]
            p = subprocess.Popen(orden, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log, creationflags=SIN_VENTANA)
            try:
                ctypes.windll.kernel32.SetPriorityClass(int(p._handle), 0x4000)  # por debajo de lo normal
            except (OSError, AttributeError):
                pass
            while p.poll() is None:
                if not seguir():
                    try:
                        p.communicate(b"q", timeout=10)  # cierre limpio del vídeo
                    except (subprocess.TimeoutExpired, OSError, ValueError):
                        p.kill()
                    break
                time.sleep(2)
            time.sleep(3)
        borradas = [] if prueba_seg else limpiar(base, cfg.get("grabacion_max_gb", 0), actual=carpeta)
        if borradas:
            log.write(f"Borradas por espacio: {', '.join(borradas)}\n")
        log.write(f"TERMINADO: {round((time.time() - empezo) / 60, 1)} min\n")
