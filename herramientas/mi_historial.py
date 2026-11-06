"""Imprime tu historial de la temporada contra unos campeones, leyendo solo la caché.

Uso: py herramientas/mi_historial.py MiCampeon Rival1 [Rival2 ...]   (el primero rival cuenta como jungla)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from porofesor import analisis as an  # noqa: E402
from porofesor import config  # noqa: E402
from porofesor.app import App  # noqa: E402


class SinRed:
    """La herramienta no debe gastar cuota: solo lee lo guardado."""

    region = plataforma = ""

    def cuenta_por_riot_id(self, *a):
        return None


def main():
    app = App(cliente=SinRed(), cliente_lol=type("Cerrado", (), {"estado": lambda s: None})())
    nombres = {v["nombre"].lower(): k for k, v in app.datos.campeones.items()}
    for rid in app.cfg["cuentas"]:
        guardada = app.cache.kv_get(f"cuenta:{rid.lower()}")
        if guardada:
            app.cuentas[guardada["puuid"]] = guardada["rid"]
    mio, *rivales = [nombres[a.lower()] for a in sys.argv[1:]]
    filas = [{"campeon": c, "pos": "JUNGLE" if i == 0 else "", "nombre_campeon": app.datos.nombre(c)} for i, c in enumerate(rivales)]
    mias = app.mis_partidas(420)
    h = an.mi_historial(set(app.cuentas), mias, mio, filas, {}, int(time.time() * 1000))
    print(f"{len(app.mis_partidas())} clasificatorias guardadas; se usan las {len(mias)} de solo/dúo")
    c = h["campeon"]
    if c:
        print(f"{app.datos.nombre(mio)}: {c['v']}V {c['n'] - c['v']}D")
    print("duelo directo:", h["vs_directo"])
    for f in h["vs"]:
        print(f"  contra {f['nombre']}: {f['v']}V {f['n'] - f['v']}D | con {app.datos.nombre(mio)}: {f['v_mio']}V {f['n_mio'] - f['v_mio']}D")


if __name__ == "__main__":
    main()
