"""Simula una partida propia: coge una partida real en vivo y sustituye a un jungla por la cuenta principal con Diana.

Sirve para ver el panel con el historial propio sin tener que jugar. Cierra antes la app normal (usan el mismo puerto y la misma cuota).
Uso: py herramientas/simular_propia.py [segundos] [--servir]   (con --servir el panel se ve en el navegador mientras dura)
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anonimizar import anonimizar  # noqa: E402
from porofesor import config  # noqa: E402
from porofesor.app import App  # noqa: E402
from porofesor.riot import Cliente  # noqa: E402

SALIDA = Path(__file__).parent / "panel_simulado.json"  # volcado del panel para mirarlo con calma
MAQUETA = Path(__file__).parent / "maquetas" / "partida.json"


class LolFalso:
    def __init__(self, rid):
        self.nombre, _, self.tag = rid.partition("#")

    def estado(self):
        return {"fase": "InProgress", "nombre": self.nombre, "tag": self.tag}

    def seleccion(self):
        return None

    def mapa(self):
        return 11

    def reloj(self):
        # Con --carga se simula la pantalla de carga; si no, una partida ya empezada (minuto 5).
        return None if "--carga" in sys.argv else 300.0


class ClienteTrucado(Cliente):
    juego = None

    def partida_activa(self, puuid):
        return self.juego if self.juego else super().partida_activa(puuid)


def main():
    espera = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    cfg = config.cargar()
    cliente = ClienteTrucado(cfg, config.leer_clave)
    app = App(cfg=cfg, cliente=cliente, cliente_lol=LolFalso(cfg["cuentas"][0]), grabador=False)
    app._comprobar_clave()
    yo = next(iter(app.cuentas))

    # A ciertas horas apenas hay Master jugando: se prueba desde arriba hacia abajo.
    entradas = []
    for liga in ("challengerleagues", "grandmasterleagues", "masterleagues"):
        lista = cliente._get(cliente.plataforma, f"/lol/league/v4/{liga}/by-queue/RANKED_SOLO_5x5")["entries"]
        random.shuffle(lista)
        entradas += lista[:50]
    juego = None
    for e in entradas:
        j = cliente.partida_activa(e["puuid"])
        if j and j.get("gameQueueConfigId") == 420 and all(p.get("puuid") for p in j["participants"]):
            juego = j
            break
    if not juego:
        print("No encontré partida en vivo")
        return 1
    jungla = next(p for p in juego["participants"] if 11 in (p["spell1Id"], p["spell2Id"]))
    jungla.update(puuid=yo, riotId=app.cuentas[yo], championId=131)
    cliente.juego = juego

    app._paso()
    s = app.sesion
    print("sesión:", s.origen, "| yo en equipo", s.mi_equipo, flush=True)
    if "--servir" in sys.argv:
        # Deja el panel a la vista en el puerto de siempre durante 'espera' segundos.
        import threading

        from porofesor import servidor

        srv = servidor.crear(app, cfg["puerto"])
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(espera)
    estado = app.estado()
    p = estado["panel"]
    SALIDA.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    # El estado entero sirve de maqueta para diseñar el panel sin partida (herramientas/maqueta.py).
    MAQUETA.parent.mkdir(exist_ok=True)
    MAQUETA.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    # Las maquetas acaban en el repositorio: nada de Riot ID, PUUID ni id de partida reales.
    anonimizar([SALIDA, MAQUETA])
    print(p["cola"], p["progreso"], "| cuota", app.estado()["cuota"])
    print("PLAN:", p["plan"])
    for a in p["avisos"]:
        print("AVISO", a["tono"], a["texto"])
    for lado in ("aliado", "rival"):
        for f in p["equipos"][lado]:
            print(lado[:3], f["rol_txt"].ljust(8), f["campeon"][:12].ljust(12), ((f["liga"] or {}).get("solo") or {}).get("txt", "..."), f["muestra"], [t["t"] for t in f["etiquetas"]], "(yo)" if f["soy_yo"] else "")
    j = p["jungla"]
    print("JUNGLA RIVAL:", j["campeon"], j["n"], j["n_campeon"], j["n_lineas"])
    for t in j["tarjetas"]:
        print("  ", t["tono"].ljust(6), t["titulo"], "→", t["valor"], "|", t["detalle"])
    for l in p["lineas"]:
        print("LÍNEA", l["linea"], l["veredicto"], "| rival:", l["rival"], "| aliado:", l["aliado"])
    h = p["historial"]
    print("HISTORIAL:", h["alcance"], h["cola_txt"], h["n"], h["mi_campeon"], h["campeon"])
    print("  duelo directo:", h["vs_directo"])
    for f in h["vs"]:
        print(f"  contra {f['nombre']}: {f['v']}V {f['n'] - f['v']}D | con Diana {f['v_mio']}V {f['n_mio'] - f['v_mio']}D")
    print("  conocidos:", h["conocidos"])
    print("RECORDATORIOS:", p["recordatorios"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
