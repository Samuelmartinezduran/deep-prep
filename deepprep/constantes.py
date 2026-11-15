"""Constantes del juego y de la API de Riot que usan varios módulos, en un solo sitio."""

# Un minuto en ms (las marcas de tiempo de Riot van en ms): 10 * MIN es el minuto 10.
MIN = 60_000
DIA_MS = 86_400_000
# Partidas más cortas no sirven para los duelos ni para tus referencias (rendiciones y remakes largos).
DURACION_MINIMA_S = 15 * 60

GRIETA = 11  # mapId de la Grieta del Invocador
ABISMO = (12, 14)  # el Abismo de los Lamentos (ARAM) y el Puente del Carnicero
ARENA = 30
SOLO_DUO, FLEXIBLE, CLASH = 420, 440, 700
COLAS = {
    0: "Partida personalizada",
    400: "Normal (reclutamiento)",
    SOLO_DUO: "Clasificatoria solo/dúo",
    430: "Normal (a ciegas)",
    FLEXIBLE: "Clasificatoria flexible",
    450: "ARAM",
    480: "Swiftplay",
    490: "Partida rápida",
    CLASH: "Clash",
    720: "Clash de ARAM",
    900: "URF",
    1020: "Uno para todos",
    1700: "Arena",
    1710: "Arena",
    1900: "URF",
    2400: "ARAM: Caos",
}
# Colas de la Grieta cuyas partidas cuentan para el historial de un jugador.
COLAS_GRIETA = {400, SOLO_DUO, 430, FLEXIBLE, 480, 490}
COLAS_NORMALES = {400, 430, 480, 490}
COLAS_ARAM = {450, 720, 2400}
COLAS_ARENA = {1700, 1710}

# Modos de juego (Ajustes > Modos de juego): en los apagados no salen ni el panel ni el overlay, y no se graba.
MODOS = {
    "clasificatoria": "Clasificatoria solo/dúo",
    "flexible": "Clasificatoria flexible",
    "normales": "Normales y partida rápida",
    "clash": "Clash",
    "aram": "ARAM",
    "arena": "Arena",
    "otros": "Otros modos",
}
# Los de la Grieta, cinco contra cinco y con posiciones: panel completo (jungla, líneas, duelo, plan), grabación y
# revisión. En los demás, solo lo básico de cada jugador: su rango y su maestría con el campeón.
MODOS_GRIETA = ("clasificatoria", "flexible", "normales", "clash")
MODOS_POR_DEFECTO = {modo: modo not in ("arena", "otros") for modo in MODOS}
# Clasificatorias: la cola de la partida -> su liga en league-v4, y cómo se dice en el panel.
LIGA_COLA = {SOLO_DUO: "RANKED_SOLO_5x5", FLEXIBLE: "RANKED_FLEX_SR"}
NOMBRE_LIGA = {SOLO_DUO: " de solo/dúo", FLEXIBLE: " flexibles"}


def modo_de(cola: int, mapa: int) -> str:
    """El modo de una partida (una clave de MODOS) por su cola y su mapa. Lo que no se reconoce va a 'otros'."""
    if cola == SOLO_DUO:
        return "clasificatoria"
    if cola == FLEXIBLE:
        return "flexible"
    if cola in COLAS_NORMALES:
        return "normales"
    if cola == CLASH:
        return "clash"
    if cola in COLAS_ARAM or mapa in ABISMO:
        return "aram"
    if cola in COLAS_ARENA or mapa == ARENA:
        return "arena"
    return "otros"


def modo_activo(modos: dict[str, bool] | None, modo: str) -> bool:
    """Si el panel sale en ese modo según Ajustes (modos guardados), o según lo de fábrica si no está guardado."""
    return bool((modos or {}).get(modo, MODOS_POR_DEFECTO.get(modo, False)))
