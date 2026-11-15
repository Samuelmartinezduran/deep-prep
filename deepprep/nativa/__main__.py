"""py -m deepprep.nativa: la interfaz nativa con la demo, para probarla y diseñar sin el LoL.

    py -m deepprep.nativa                                   la ventana (con la barra de escenas de la demo)
    py -m deepprep.nativa --vista revisiones --escena juego empieza en esa pestaña y esa escena
    py -m deepprep.nativa --rol MIDDLE                      jugando en esa posición (TOP, MIDDLE, BOTTOM, UTILITY)
    py -m deepprep.nativa --sin-barra                       sin la barra de escenas de la demo (las capturas del README)
    py -m deepprep.nativa --captura salida.png [w h]        una captura (1500 por 950) sin enseñar la ventana
        --overlay                                           ...del overlay en vez de la ventana principal
        --minuto 14                                         ...con el detalle de ese minuto en el gráfico de oro
    py -m deepprep.nativa --medir 8                         a los 8 s escribe la memoria que gasta y se cierra

La app de verdad la abre py -m deepprep. Aquí, siempre la demo: sin el LoL ni clave, en la carpeta temporal de
la demo, que se borra al salir (--demo, antes de que config elija la carpeta de los datos).
"""

import sys

if "--demo" not in sys.argv:
    sys.argv.append("--demo")

import ctypes
from ctypes import wintypes as wt
from pathlib import Path

from .. import config
from ..demo import AppDemo, borrar_carpeta


def opcion(nombre: str, n: int = 1) -> list[str]:
    """Los n valores que siguen a --nombre ([] si no está)."""
    if nombre not in sys.argv:
        return []
    i = sys.argv.index(nombre)
    return [a for a in sys.argv[i + 1 : i + 1 + n] if not a.startswith("--")]


def memoria() -> tuple[float, float]:
    """(memoria privada, memoria en uso) de este proceso, en MB: lo mismo que enseña el Administrador de tareas."""

    class Memoria(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS_EX
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [
            (n, ctypes.c_size_t)
            for n in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
                "PrivateUsage",
            )
        ]

    m = Memoria()
    m.cb = ctypes.sizeof(m)
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wt.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
    k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(m), m.cb)
    return m.PrivateUsage / 2**20, m.WorkingSetSize / 2**20


def main() -> int:
    from PySide6.QtGui import QGuiApplication

    from .ventanas import VentanasQt, capturar

    QGuiApplication(sys.argv)  # antes que los temporizadores de --medir

    escena = (opcion("--escena") or ["carga"])[0]
    demo = AppDemo(config.DATOS, escena=escena, barra="--sin-barra" not in sys.argv)
    for rol in opcion("--rol"):
        demo.elegir_rol(rol.upper())
    vista = (opcion("--vista") or ["partida"])[0]
    minuto = float((opcion("--minuto") or ["-1"])[0])
    try:
        captura = opcion("--captura", 3)
        if captura:
            ancho, alto = (int(captura[1]), int(captura[2])) if len(captura) == 3 else (1500, 950)
            return capturar(
                demo,
                Path(captura[0]).resolve(),
                ancho,
                alto,
                overlay_="--overlay" in sys.argv,
                titulo="Deep Prep · demo",
                demo=True,
                vista=vista,
                minuto_fijo=minuto,
            )
        v = VentanasQt(demo, titulo="Deep Prep · demo", demo=True, vista=vista, minuto_fijo=minuto)
        medir = opcion("--medir")
        if medir:
            from PySide6.QtCore import QTimer

            def medir_y_salir() -> None:
                privada, en_uso = memoria()
                print(f"Memoria: {privada:.0f} MB privada, {en_uso:.0f} MB en uso")
                app = QGuiApplication.instance()
                if app:
                    app.quit()

            QTimer.singleShot(int(float(medir[0]) * 1000), medir_y_salir)
        return v.arrancar()
    finally:
        borrar_carpeta(config.DATOS)


sys.exit(main())
