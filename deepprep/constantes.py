"""Constantes del juego y de la API de Riot que usan varios módulos, en un solo sitio."""

# Un minuto en ms (las marcas de tiempo de Riot van en ms): 10 * MIN es el minuto 10.
MIN = 60_000
DIA_MS = 86_400_000
# Partidas más cortas no sirven para los duelos ni para tus referencias (rendiciones y remakes largos).
DURACION_MINIMA_S = 15 * 60

GRIETA = 11  # mapId de la Grieta del Invocador
SOLO_DUO, FLEXIBLE = 420, 440
COLAS = {
    400: "Normal (reclutamiento)",
    SOLO_DUO: "Clasificatoria solo/dúo",
    430: "Normal (a ciegas)",
    FLEXIBLE: "Clasificatoria flexible",
    450: "ARAM",
    480: "Swiftplay",
    490: "Partida rápida",
    700: "Clash",
}
# Colas de la Grieta cuyas partidas cuentan para el historial de un jugador.
COLAS_GRIETA = {400, SOLO_DUO, 430, FLEXIBLE, 480, 490}
# Clasificatorias: la cola de la partida -> su liga en league-v4, y cómo se dice en el panel.
LIGA_COLA = {SOLO_DUO: "RANKED_SOLO_5x5", FLEXIBLE: "RANKED_FLEX_SR"}
NOMBRE_LIGA = {SOLO_DUO: " de solo/dúo", FLEXIBLE: " flexibles"}
