"""Busca a alguien de Master que esté en partida ahora mismo, para probar el panel sin jugar.

Uso: py herramientas/buscar_en_vivo.py [intentos]
Imprime el Riot ID de un jugador en partida clasificatoria en la Grieta.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from porofesor import config  # noqa: E402
from porofesor.riot import Cliente  # noqa: E402


def main():
    intentos = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    cfg = config.cargar()
    cliente = Cliente(cfg, config.leer_clave)
    liga = cliente._get(cliente.plataforma, "/lol/league/v4/masterleagues/by-queue/RANKED_SOLO_5x5")
    entradas = liga["entries"]
    random.shuffle(entradas)
    for e in entradas[:intentos]:
        juego = cliente.partida_activa(e["puuid"])
        if juego and juego.get("gameQueueConfigId") in (420, 440) and juego.get("mapId") == 11:
            yo = next(p for p in juego["participants"] if p["puuid"] == e["puuid"])
            print(yo["riotId"])
            return 0
    print("Nadie en partida en esta tanda; prueba otra vez.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
