"""Revisión de una partida propia ya terminada. Funciones puras: no tocan red ni disco.

Riot anima justo a esto: jugar primero y analizar después. Aquí sí se sacan conclusiones.
"""

from . import analisis as an

MONSTRUOS = {"DRAGON": "Dragón", "BARON_NASHOR": "Barón", "RIFTHERALD": "Heraldo", "HORDE": "Larvas", "ATAKHAN": "Atakhan"}
DRAGONES = {
    "FIRE_DRAGON": "infernal",
    "WATER_DRAGON": "oceánico",
    "EARTH_DRAGON": "de montaña",
    "AIR_DRAGON": "de nube",
    "HEXTECH_DRAGON": "hextech",
    "CHEMTECH_DRAGON": "quimtech",
    "ELDER_DRAGON": "ancestral",
}
# Un objetivo que el rival hace poco después de una muerte tuya cuenta como perdido por ella.
VENTANA_OBJETIVO_MS = 90_000
TROZO_S = 300  # la grabación va en trozos de 5 minutos


def reducir_linea_completa(t):
    """Línea de tiempo entera (no solo los 15 primeros minutos): estado por minuto, kills y monstruos."""
    info = t["info"]
    pos, est = {}, {}
    for f in info["frames"]:
        for pid, pf in f.get("participantFrames", {}).items():
            p = pf.get("position") or {}
            pos.setdefault(pid, []).append([p.get("x", 0), p.get("y", 0)])
            est.setdefault(pid, []).append(
                [
                    pf.get("totalGold", 0),
                    pf.get("xp", 0),
                    pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0),
                    pf.get("level", 1),
                ]
            )
    kills, monstruos = [], []
    for f in info["frames"]:
        for e in f.get("events", []):
            if e["type"] == "CHAMPION_KILL":
                p = e.get("position") or {}
                kills.append(
                    [
                        e["timestamp"],
                        p.get("x", 0),
                        p.get("y", 0),
                        e.get("killerId", 0),
                        e.get("victimId", 0),
                        e.get("assistingParticipantIds") or [],
                    ]
                )
            elif e["type"] == "ELITE_MONSTER_KILL":
                monstruos.append(
                    [
                        e["timestamp"],
                        e.get("monsterType", ""),
                        e.get("monsterSubType") or "",
                        e.get("killerId", 0),
                        e.get("killerTeamId", 0),
                        e.get("assistingParticipantIds") or [],
                    ]
                )
    return {"id": t["metadata"]["matchId"], "pos": pos, "est": est, "kills": kills, "monstruos": monstruos}


def donde(x, y, mi_equipo):
    tipo, lado, mitad = an.zona(x, y)
    lado_txt = "arriba" if lado == "sup" else "abajo"
    if tipo == "base":
        return "en tu base" if mitad == mi_equipo else "en la base rival"
    if tipo in ("top", "mid", "bot"):
        return f"en {tipo}"
    if tipo == "rio":
        return f"en el río ({lado_txt})"
    return f"en tu jungla ({lado_txt})" if mitad == mi_equipo else f"en la jungla rival ({lado_txt})"


def nombre_monstruo(tipo, subtipo):
    base = MONSTRUOS.get(tipo, tipo.capitalize())
    if tipo == "DRAGON" and subtipo in DRAGONES:
        return f"{base} {DRAGONES[subtipo]}"
    return base


def nombre_trozo(serie, trozo):
    """Archivo de un trozo de la grabación (lo que escribe grabacion.py: r01_seg_000.mkv, ...)."""
    return f"r{serie:02d}_seg_{trozo:03d}.mkv"


def en_grabacion(ms, desfase_s):
    """En qué serie de la grabación cae un momento de la partida y en qué segundo de ella: (serie, s), o None.

    desfase_s: {serie: segundos que lleva grabados antes del 0:00 de la partida}; negativo si la serie empezó
    ya jugando (ffmpeg se relanza a media partida, p. ej. al cambiar la resolución). Un número solo es la
    serie 1, como antes de que hubiera series. El momento va en la última serie que ya había empezado.
    """
    if desfase_s is None:
        return None
    series = desfase_s if isinstance(desfase_s, dict) else {1: desfase_s}
    empezadas = [(n, ms / 1000 + d) for n, d in series.items() if ms / 1000 + d >= 0]
    return min(empezadas, key=lambda s: s[1]) if empezadas else None


def en_video(ms, desfase_s):
    """Dónde cae un momento de la partida en la grabación: (trozo, 'm:ss' dentro del trozo), o None."""
    donde = en_grabacion(ms, desfase_s)
    if not donde:
        return None
    serie, t = donde
    trozo = int(t // TROZO_S)
    dentro = int(t % TROZO_S)
    return {"archivo": nombre_trozo(serie, trozo), "en": f"{dentro // 60}:{dentro % 60:02d}"}


def _al(linea, pid, minuto):
    est = linea["est"].get(str(pid)) or []
    return est[minuto] if len(est) > minuto else None


def revisar(partida, linea, yo_puuid, nombre_campeon, panel=None, desfase_s=None):
    """Revisión de la partida desde el punto de vista de yo_puuid.

    nombre_campeon: función id -> nombre. panel: el panel tal y como estaba al empezar (para comparar).
    desfase_s: segundos de grabación que hay antes del 0:00 de la partida, por serie (ver en_grabacion; None si
    no hay grabación).
    """
    yo = an.jugador_en(partida, yo_puuid)
    if not yo:
        return None
    pid, equipo = yo["pid"], yo["equipo"]
    por_pid = {j["pid"]: j for j in partida["jug"]}
    minutos = max(1, partida["duracion"] / 60)
    jr = next((j for j in partida["jug"] if j["pos"] == "JUNGLE" and j["equipo"] != equipo), None)
    # Con quién compararte: tu rival de posición (en jungla, el jungla rival).
    directo = next((j for j in partida["jug"] if yo["pos"] and j["pos"] == yo["pos"] and j["equipo"] != equipo), None) or jr

    def campeon(p):
        return nombre_campeon(por_pid[p]["campeon"]) if p in por_pid else "Torre o súbditos"

    return {
        "id": partida["id"],
        "fecha": partida["creacion"],
        "cola": partida["cola"],
        "duracion": an.mmss(partida["duracion"] * 1000),
        "gana": yo["gana"],
        "campeon": nombre_campeon(yo["campeon"]),
        "campeon_id": yo["campeon"],
        "pos": yo["pos"],
        "equipo": equipo,
        "kda": [yo["k"], yo["d"], yo["a"]],
        "cs_min": round(yo["cs"] / minutos, 1),
        "oro": yo["oro"],
        "dano": yo["dano"],
        "kp": round(yo["ch"].get("killParticipation", 0) * 100),
        "dano_pct": round(yo["ch"].get("teamDamagePercentage", 0) * 100),
        "vision": yo["vision"],
        "wards": yo["wards"],
        "control": yo["control"],
        "muertes": _muertes(linea, pid, equipo, campeon, set(por_pid), desfase_s),
        "comparacion": _comparacion(linea, pid, directo, nombre_campeon) if directo else None,
        "objetivos": _objetivos(linea["monstruos"], pid, equipo),
        "prevision": _prevision(panel, linea, partida, equipo, jr),
    }


def _muertes(linea, pid, equipo, campeon, pids, desfase_s):
    """Tus muertes: dónde, quién, si costaron un objetivo y en qué punto de la grabación caen.

    campeon(pid): nombre del campeón de ese jugador. pids: los de los jugadores (lo demás es una torre o súbditos).
    """
    monstruos = linea["monstruos"]
    muertes = []
    for t, x, y, asesino, victima, ayudas in linea["kills"]:
        if victima != pid:
            continue
        perdido = next(
            (m for m in monstruos if t < m[0] <= t + VENTANA_OBJETIVO_MS and m[4] and m[4] != equipo),
            None,
        )
        muertes.append(
            {
                "t": an.mmss(t),
                "ms": t,
                "x": x,
                "y": y,
                "donde": donde(x, y, equipo),
                "asesino": campeon(asesino),
                "ayudas": [campeon(a) for a in ayudas],
                "rivales": (1 if asesino in pids else 0) + len(ayudas),
                "perdido": f"{nombre_monstruo(perdido[1], perdido[2])} rival {an.mmss(perdido[0] - t)} después"
                if perdido
                else "",
                "video": en_video(t, desfase_s),
            }
        )
    return muertes


def _objetivos(monstruos, pid, equipo):
    return [
        {
            "t": an.mmss(t),
            "nombre": nombre_monstruo(tipo, subtipo),
            "tuyo": equipo_m == equipo,
            "participaste": pid == asesino or pid in ayudas,
        }
        for t, tipo, subtipo, asesino, equipo_m, ayudas in monstruos
    ]


def _comparacion(linea, pid, directo, nombre_campeon):
    """Tu oro, experiencia, CS y nivel al 10 y al 15 al lado de los de tu rival directo, o None sin datos."""
    filas = {}
    for minuto in (10, 15):
        mio, suyo = _al(linea, pid, minuto), _al(linea, directo["pid"], minuto)
        if mio and suyo:
            filas[str(minuto)] = {
                "oro": [mio[0], suyo[0]],
                "xp": [mio[1], suyo[1]],
                "cs": [mio[2], suyo[2]],
                "nivel": [mio[3], suyo[3]],
            }
    return {"rival": nombre_campeon(directo["campeon"]), "minutos": filas} if filas else None


def _prevision(panel, linea, partida, equipo, jr):
    """Lo que el panel decía al empezar frente a lo que pasó."""
    if not panel:
        return []
    filas = []
    gank = panel.get("gank")
    if gank and jr:
        real = an.primer_gank(linea, jr["pid"])
        filas.append(
            {
                "tema": "Primer gank del jungla rival",
                "dijo": f"{gank['linea']} ({gank['veces']} de {gank['n']} partidas)",
                "paso": f"{real[1]} al {an.mmss(real[0])}" if real else "ninguno antes del 10",
                "acierto": bool(real) and real[1] == gank["linea"],
            }
        )
    lineas = panel.get("lineas") or []
    if lineas and lineas[0].get("veredicto") == "Aquí se equivocan":
        nombre = lineas[0]["linea"]
        posiciones = {"top": ("TOP",), "mid": ("MIDDLE",), "bot": ("BOTTOM", "UTILITY")}.get(nombre, ())
        rivales = [j for j in partida["jug"] if j["equipo"] != equipo and j["pos"] in posiciones]
        muertes = sum(an.muertes_antes(linea, j["pid"], 15) for j in rivales)
        normal = an.MUERTES15_NORMAL * len(rivales)
        filas.append(
            {
                "tema": f"Rival de {nombre} con más errores",
                "dijo": "el que más fallaba en sus partidas",
                "paso": f"{muertes} muertes antes del 15 (lo normal: {an.num(normal, 0)})",
                "acierto": muertes > normal,
            }
        )
    return filas


# --- tendencias de la temporada ------------------------------------------------------------------
def _fila(nombre, juegos):
    return {"nombre": nombre, "n": len(juegos), "v": sum(1 for g in juegos if g)}


def tendencias(partidas, mis_puuids, nombre_campeon, hora_local):
    """Patrones de tus clasificatorias de la temporada. hora_local: función ms -> hora (0-23)."""
    juegos = []  # de la más antigua a la más reciente
    for m in reversed(an.validas(partidas)):
        yo = next((j for j in m["jug"] if j["puuid"] in mis_puuids), None)
        if yo:
            juegos.append((m, yo))
    if not juegos:
        return None
    primera, tras_victoria, tras_derrota = _por_sesion(juegos)
    franjas = {"Mañana (6-14 h)": [], "Tarde (14-20 h)": [], "Noche (20-24 h)": [], "Madrugada (0-6 h)": []}
    duraciones = {"Menos de 25 min": [], "25 a 35 min": [], "Más de 35 min": []}
    directos = {}  # (campeón rival, posición) -> resultados, contra tu rival de posición
    for m, yo in juegos:
        franjas[_franja(hora_local(m["creacion"]))].append(yo["gana"])
        minutos = m["duracion"] / 60
        duraciones["Menos de 25 min" if minutos < 25 else "25 a 35 min" if minutos <= 35 else "Más de 35 min"].append(yo["gana"])
        if yo["pos"]:
            rival = next((j for j in m["jug"] if j["pos"] == yo["pos"] and j["equipo"] != yo["equipo"]), None)
            if rival:
                directos.setdefault((rival["campeon"], yo["pos"]), []).append(yo["gana"])
    frecuentes = sorted(directos.items(), key=lambda x: len(x[1]), reverse=True)[:8]
    varias_pos = len({p for _, p in directos}) > 1
    return {
        "n": len(juegos),
        "sesion": [
            _fila("Primera partida de la sesión", primera),
            _fila("Después de ganar", tras_victoria),
            _fila("Después de perder", tras_derrota),
        ],
        "franjas": [_fila(k, v) for k, v in franjas.items() if v],
        "duracion": [_fila(k, v) for k, v in duraciones.items() if v],
        # Si juegas varias posiciones se dice en cuál fue cada duelo.
        "rivales": [
            dict(_fila(f"{nombre_campeon(c)} ({an.NOMBRE_POS.get(p, p)})" if varias_pos else nombre_campeon(c), v), campeon=c)
            for (c, p), v in frecuentes
        ],
    }


def _por_sesion(juegos):
    """Resultados de la primera partida de cada sesión, de las de después de ganar y de las de después de perder."""
    primera, tras_victoria, tras_derrota = [], [], []
    for i, (m, yo) in enumerate(juegos):
        anterior = juegos[i - 1] if i else None
        # Misma sesión: empezó menos de 2 horas después de acabar la anterior.
        seguida = anterior and m["creacion"] - (anterior[0]["creacion"] + anterior[0]["duracion"] * 1000) < 2 * 3600 * 1000
        if seguida:
            (tras_victoria if anterior[1]["gana"] else tras_derrota).append(yo["gana"])
        else:
            primera.append(yo["gana"])
    return primera, tras_victoria, tras_derrota


def _franja(h):
    return "Madrugada (0-6 h)" if h < 6 else "Mañana (6-14 h)" if h < 14 else "Tarde (14-20 h)" if h < 20 else "Noche (20-24 h)"


def mapa_muertes(revisiones):
    """Tus muertes de varias revisiones, todas vistas desde la base azul (abajo a la izquierda)."""
    out = []
    for r in revisiones:
        if not r or "equipo" not in r:
            continue
        for m in r["muertes"]:
            if "x" not in m:
                continue
            x, y = (m["x"], m["y"]) if r["equipo"] == 100 else an.espejo(m["x"], m["y"])
            out.append(
                {
                    "x": x,
                    "y": y,
                    "ms": m["ms"],
                    "t": m["t"],
                    "id": r["id"],
                    "campeon": r["campeon"],
                    "gana": r["gana"],
                    "asesino": m["asesino"],
                }
            )
    return out
