"""Recortes de tus muertes sacados de la grabación de la partida, para revisarlas sin buscar en el vídeo.

La grabación va en trozos de 5 minutos (r01_seg_000.mkv, ...): un recorte que cae entre dos trozos los une.
Si ffmpeg se relanzó a media partida, lo de después está en otra serie (r02_seg_000.mkv, ...).
Se codifica con prioridad mínima y pocos hilos para no molestar si ya estás en otra partida.
"""

import subprocess
from pathlib import Path

from .revision import TROZO_S, en_grabacion, nombre_trozo
from .sistema import SIN_VENTANA

ANTES_S = 20  # lo que lleva a la muerte
DESPUES_S = 4
PRIORIDAD_MINIMA = getattr(subprocess, "IDLE_PRIORITY_CLASS", 0)


def tramo(ms, desfase_s):
    """(trozos de la grabación, segundo de inicio dentro del primero, duración) del recorte de una muerte.

    desfase_s: como en revision.en_grabacion (por serie; un número es la serie 1). Devuelve None si la muerte es
    de antes de que empezara la grabación. El recorte no sale de la serie de la muerte: si la serie empezó menos
    de ANTES_S antes, el recorte empieza con ella.
    """
    donde = en_grabacion(ms, desfase_s)
    if not donde:
        return None
    serie, t = donde
    inicio = max(0.0, t - ANTES_S)
    fin = t + DESPUES_S
    primero, ultimo = int(inicio // TROZO_S), int(fin // TROZO_S)
    archivos = [nombre_trozo(serie, k) for k in range(primero, ultimo + 1)]
    return archivos, round(inicio - primero * TROZO_S, 2), round(fin - inicio, 2)


def nombre_clip(i, muerte):
    return f"{i + 1:02d}_{muerte['t'].replace(':', '-')}.mp4"


def lista_concat(rutas):
    """Texto del archivo de concat de ffmpeg con estos trozos.

    Cada ruta va entre comillas simples. Una comilla dentro de la ruta (C:/Users/O'Neill/...) no se puede poner
    tal cual: se cierra la comilla, va la comilla escapada (\\') y se vuelve a abrir, como pide ffmpeg.
    """
    return "".join("file '{}'\n".format(Path(r).as_posix().replace("'", "'\\''")) for r in rutas)


def orden_ffmpeg(ffmpeg, rutas, desde, duracion, destino, lista):
    """Orden de ffmpeg para un recorte; con dos trozos, 'lista' es el archivo de concat que hay que escribir."""
    if len(rutas) == 1:
        entrada = ["-ss", f"{desde}", "-i", str(rutas[0])]
    else:
        entrada = ["-f", "concat", "-safe", "0", "-i", str(lista), "-ss", f"{desde}"]
    return [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
        "-y",
        *entrada,
        "-t",
        f"{duracion}",
        "-vf",
        "scale=-2:720",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-threads",
        "2",
        "-an",
        "-movflags",
        "+faststart",
        str(destino),
    ]


def recortar(ffmpeg, carpeta, i, muerte, desfase_s):
    """Hace el recorte de una muerte y devuelve su ruta, o None si la grabación no la cubre."""
    carpeta = Path(carpeta)
    corte = tramo(muerte["ms"], desfase_s)
    if not corte:
        return None
    archivos, desde, duracion = corte
    rutas = [carpeta / a for a in archivos]
    if not all(r.is_file() for r in rutas):
        return None
    salida = carpeta / "muertes"
    salida.mkdir(exist_ok=True)
    destino = salida / nombre_clip(i, muerte)
    if destino.is_file() and destino.stat().st_size:
        return destino
    lista = salida / f"{destino.stem}.txt"
    if len(rutas) > 1:
        lista.write_text(lista_concat(rutas), encoding="utf-8")
    try:
        subprocess.run(
            orden_ffmpeg(ffmpeg, rutas, desde, duracion, destino, lista),
            check=True,
            timeout=600,
            capture_output=True,
            creationflags=SIN_VENTANA | PRIORIDAD_MINIMA,
        )
    except (subprocess.SubprocessError, OSError) as e:
        print(f"No se pudo recortar la muerte {muerte['t']}: {e}")
        destino.unlink(missing_ok=True)
        return None
    finally:
        lista.unlink(missing_ok=True)
    return destino
