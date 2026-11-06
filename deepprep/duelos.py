"""El duelo de tu campeón contra su rival directo, medido en partidas de Master+. Funciones puras.

De cada partida con línea de tiempo salen diez registros, uno por jugador, cada uno mirado desde ese
jugador ('a') contra el de su misma posición en el otro equipo ('b'). Luego, para un duelo concreto,
se buscan los datos que no son de manual: quién gana las peleas antes y después del 6, cuánto pesa ir
por delante, qué hacen distinto los que ganan, dónde se muere, si escala, y tus números al lado.
"""

import statistics
from collections import Counter

from . import analisis as an

MIN = 60000
POSICIONES = an.POSICIONES
# Peleas "pequeñas": las dos del duelo implicadas y como mucho cuatro jugadores en total.
MAX_IMPLICADOS = 4
FIN_PELEAS = 15 * MIN

# Mínimos para enseñar un dato: con menos, el porcentaje es ruido.
MIN_PARTIDAS = 12
MIN_PELEAS = 10
MIN_GRUPO = 8


# --- extracción (de la partida y la línea de tiempo de Riot a registros pequeños) --------------------
def _zona(pos, equipo):
    tipo, lado, mitad = an.zona(pos.get("x", 0), pos.get("y", 0))
    return [tipo, lado, mitad == equipo]


def extraer(partida, linea, legendarios):
    """Diez registros (uno por jugador con rival de posición) de una partida de la Grieta.

    legendarios: ids de objetos que cuentan como primer objeto completo.
    """
    info, tl = partida["info"], linea["info"]
    jug = info["participants"]
    if info.get("gameDuration", 0) < 15 * 60 or any(p.get("gameEndedInEarlySurrender") for p in jug):
        return []
    por_pos = {}
    for p in jug:
        por_pos.setdefault((p["teamId"], p.get("teamPosition") or ""), []).append(p)
    parejas = []
    for pos in POSICIONES:
        azul, rojo = por_pos.get((100, pos), []), por_pos.get((200, pos), [])
        if len(azul) == 1 and len(rojo) == 1:
            parejas += [(pos, azul[0], rojo[0]), (pos, rojo[0], azul[0])]
    if not parejas:
        return []

    pid_equipo = {p["participantId"]: p["teamId"] for p in jug}
    nivel = {p["participantId"]: 1 for p in jug}
    frames = tl["frames"]
    # Recorrido único de los eventos; cada kill se guarda con los niveles de ese momento.
    kills, compras, habilidades, monstruos = [], {}, {}, []
    for f in frames:
        for e in f.get("events", []):
            ty = e["type"]
            if ty == "LEVEL_UP":
                nivel[e["participantId"]] = e["level"]
            elif ty == "CHAMPION_KILL":
                implicados = {e.get("killerId", 0), e["victimId"], *(e.get("assistingParticipantIds") or [])} - {0}
                kills.append(
                    (e["timestamp"], e.get("killerId", 0), e["victimId"], implicados, e.get("position") or {}, dict(nivel))
                )
            elif ty == "ITEM_PURCHASED" and e.get("itemId") in legendarios:
                compras.setdefault(e["participantId"], [e["itemId"], round(e["timestamp"] / MIN, 1)])
            elif ty == "SKILL_LEVEL_UP" and e.get("levelUpType", "NORMAL") == "NORMAL":
                habilidades.setdefault(e["participantId"], []).append(e["skillSlot"])
            elif ty == "ELITE_MONSTER_KILL":
                monstruos.append((e["timestamp"], e.get("monsterType", ""), e.get("killerTeamId", 0)))

    def marco(minuto, pid):
        if minuto >= len(frames):
            return None
        return frames[minuto]["participantFrames"].get(str(pid))

    version = ".".join(info.get("gameVersion", "").split(".")[:2])
    out = []
    for pos, a, b in parejas:
        A, B, eq = a["participantId"], b["participantId"], a["teamId"]
        dif = {}
        for minuto in (5, 10, 15):
            fa, fb = marco(minuto, A), marco(minuto, B)
            if fa and fb:
                cs = lambda f: f.get("minionsKilled", 0) + f.get("jungleMinionsKilled", 0)  # noqa: E731
                dif[str(minuto)] = [fa["totalGold"] - fb["totalGold"], fa["xp"] - fb["xp"], cs(fa) - cs(fb)]
        f10 = marco(10, A)
        peleas, muertes, m10, ka10 = [], [], 0, 0
        for ts, _killer, victima, implicados, posicion, niveles in kills:
            if ts < FIN_PELEAS and A in implicados and B in implicados and len(implicados) <= MAX_IMPLICADOS:
                gana = pid_equipo.get(victima) != eq
                peleas.append([round(ts / MIN, 1), niveles[A], niveles[B], int(gana), len(implicados), *_zona(posicion, eq)])
            if victima == A and ts < FIN_PELEAS:
                muertes.append([round(ts / MIN, 1), int(B in implicados), *_zona(posicion, eq)])
                m10 += ts < 10 * MIN
            elif A in implicados and victima != A and ts < 10 * MIN:
                ka10 += 1
        orden = habilidades.get(A, [])
        hab = (
            "".join("QWER"[s - 1] for s in orden[:3])
            + ">"
            + "".join(sorted("QWE", key=lambda s: (-orden[:11].count("QWER".index(s) + 1), "QWE".index(s))))
            if orden
            else ""
        )
        estilos = (a.get("perks") or {}).get("styles") or []
        r = {
            "pos": pos,
            "a": a["championId"],
            "b": b["championId"],
            "puuid": a.get("puuid", ""),
            "g": int(bool(a.get("win"))),
            "dur": round(info["gameDuration"] / 60, 1),
            "v": version,
            "dif": dif,
            "cs10": (f10.get("minionsKilled", 0) + f10.get("jungleMinionsKilled", 0)) if f10 else None,
            "peleas": peleas,
            "muertes": muertes,
            "m10": m10,
            "ka10": ka10,
            "item": compras.get(A),
            "runa": [estilos[0]["selections"][0]["perk"], estilos[1]["style"]] if len(estilos) >= 2 else None,
            "hab": hab,
        }
        if pos == "JUNGLE":
            propios = [m for m in monstruos if m[2] == eq]
            dragones = [m for m in monstruos if m[1] == "DRAGON"]
            r["larvas"] = sum(1 for m in propios if m[1] == "HORDE")
            r["drag1"] = int(dragones[0][2] == eq) if dragones else None
            fa, fb = marco(2, A), marco(2, B)
            if fa and fb:
                # Mismo lado del mapa (arriba o abajo de mid) a los 2:00: empezaron por el mismo lado.
                arriba = lambda f: (f.get("position") or {}).get("y", 0) > (f.get("position") or {}).get("x", 0)  # noqa: E731
                r["mismo_lado"] = int(arriba(fa) == arriba(fb))
        out.append(r)
    return out


# --- análisis de un duelo ---------------------------------------------------------------------------------
def _pct(v, n):
    return round(100 * v / n) if n else 0


def _media(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def _efecto(ganan, pierden):
    """Diferencia entre medias en desviaciones típicas (d de Cohen): >0,3 ya se nota."""
    ganan, pierden = [x for x in ganan if x is not None], [x for x in pierden if x is not None]
    if len(ganan) < MIN_GRUPO or len(pierden) < MIN_GRUPO:
        return 0.0
    todo = ganan + pierden
    sd = statistics.pstdev(todo)
    return (statistics.fmean(ganan) - statistics.fmean(pierden)) / sd if sd else 0.0


def nombre_zona(z):
    tipo, lado, propia = z
    arriba = "de arriba" if lado == "sup" else "de abajo"
    if tipo == "jungla":
        return f"{'tu' if propia else 'su'} jungla {arriba}"
    if tipo == "rio":
        return f"el río {arriba}"
    if tipo == "base":
        return "tu base" if propia else "su base"
    return {"top": "la línea de top", "mid": "mid", "bot": "la línea de bot"}.get(tipo, tipo)


def _num(x, dec=1):
    return an.num(x, dec)


def analizar(registros, mios, nombre_a, nombre_b, pos, nombre_objeto=str, nombre_runa=str):
    """Lo que dicen los registros de un duelo (a contra b en pos), con tus partidas al lado.

    registros: los de Master+ (desde el lado de a). mios: tus registros con ese campeón en esa posición
    (contra cualquiera), para comparar tus hábitos con los de quien gana este duelo.
    Devuelve None si no hay datos suficientes ni para el porcentaje de victorias.
    """
    n = len(registros)
    if n < MIN_PARTIDAS:
        return {"n": n, "datos": [], "build": None, "tu": None, "poco": True}
    ganan = [r for r in registros if r["g"]]
    pierden = [r for r in registros if not r["g"]]
    datos = []  # (peso, texto, detalle)

    # 1. Peleas entre los dos, por nivel.
    peleas = [p for r in registros for p in r["peleas"]]
    antes = [p for p in peleas if p[1] < 6]
    despues = [p for p in peleas if p[1] >= 6]
    if len(antes) >= MIN_PELEAS and len(despues) >= MIN_PELEAS:
        pa, pd = _pct(sum(p[3] for p in antes), len(antes)), _pct(sum(p[3] for p in despues), len(despues))
        datos.append(
            (
                abs(pa - pd) + abs(pa - 50) / 2,
                f"{nombre_a} gana el {pa}% de las peleas con {nombre_b} antes de su 6; desde el 6, el {pd}%.",
                f"{len(antes)} y {len(despues)} peleas de 2 a 4 jugadores antes del 15",
            )
        )
    elif len(peleas) >= MIN_PELEAS:
        pt = _pct(sum(p[3] for p in peleas), len(peleas))
        datos.append(
            (
                abs(pt - 50),
                f"{nombre_a} gana el {pt}% de las peleas con {nombre_b} antes del 15.",
                f"{len(peleas)} peleas de 2 a 4 jugadores",
            )
        )
    ventaja = [p for p in peleas if p[1] > p[2]]
    igual = [p for p in peleas if p[1] == p[2]]
    if len(ventaja) >= MIN_PELEAS and len(igual) >= MIN_PELEAS:
        pv, pi = _pct(sum(p[3] for p in ventaja), len(ventaja)), _pct(sum(p[3] for p in igual), len(igual))
        if pv - pi >= 10:
            datos.append(
                (
                    pv - pi,
                    f"Con un nivel más que {nombre_b}, {nombre_a} gana el {pv}% de las peleas; a la par, el {pi}%.",
                    f"{len(ventaja)} y {len(igual)} peleas",
                )
            )

    # 2. Cuánto pesa ir por delante al 10.
    con10 = [r for r in registros if "10" in r["dif"]]
    delante = [r for r in con10 if r["dif"]["10"][0] >= 500]
    detras = [r for r in con10 if r["dif"]["10"][0] <= -500]
    if len(delante) >= MIN_GRUPO and len(detras) >= MIN_GRUPO:
        wd, wt = _pct(sum(r["g"] for r in delante), len(delante)), _pct(sum(r["g"] for r in detras), len(detras))
        datos.append(
            (
                abs(wd - wt) / 2,
                f"{nombre_a} con +500 de oro sobre {nombre_b} al 10 gana el {wd}% de las partidas; con −500, el {wt}%.",
                f"{len(delante)} y {len(detras)} partidas",
            )
        )

    # 3. Si escala o se decide pronto.
    cortas = [r for r in registros if r["dur"] < 25]
    largas = [r for r in registros if r["dur"] >= 32]
    if len(cortas) >= MIN_GRUPO and len(largas) >= MIN_GRUPO:
        wc, wl = _pct(sum(r["g"] for r in cortas), len(cortas)), _pct(sum(r["g"] for r in largas), len(largas))
        if abs(wc - wl) >= 10:
            datos.append(
                (
                    abs(wc - wl),
                    f"{nombre_a} gana el {wc}% de las partidas que acaban antes del 25 y el {wl}% de las que pasan del 32.",
                    f"{len(cortas)} y {len(largas)} partidas",
                )
            )

    # 4. Qué hacen distinto los que ganan este duelo.
    habitos = [
        ("muertes antes del 10", lambda r: r["m10"], 1),
        (f"peleas con {nombre_b} antes del 6", lambda r: sum(1 for p in r["peleas"] if p[1] < 6), 1),
        ("kills y asistencias antes del 10", lambda r: r["ka10"], 1),
    ]
    if pos == "JUNGLE":
        habitos.append(("CS al 10", lambda r: r["cs10"], 0))
    elif pos != "UTILITY":
        habitos.append((f"diferencia de CS con {nombre_b} al 10", lambda r: (r["dif"].get("10") or [None] * 3)[2], 1))
    if pos == "JUNGLE":
        habitos += [("larvas", lambda r: r.get("larvas"), 1), ("primer dragón", lambda r: r.get("drag1"), None)]
    candidatos = []
    for nombre, fn, dec in habitos:
        d = _efecto([fn(r) for r in ganan], [fn(r) for r in pierden])
        if abs(d) >= 0.3:
            candidatos.append((abs(d), nombre, fn, dec))
    for d, nombre, fn, dec in sorted(candidatos, reverse=True)[:2]:
        mg, mp = _media(fn(r) for r in ganan), _media(fn(r) for r in pierden)
        if dec is None:
            texto = f"Primer dragón para tu equipo: {round(100 * mg)}% en las que gana {nombre_a}, {round(100 * mp)}% en las que pierde."
        else:
            texto = f"{nombre[0].upper() + nombre[1:]}: {_num(mg, dec)} en las que gana {nombre_a}, {_num(mp, dec)} en las que pierde."
        datos.append((25 * d, texto, f"{len(ganan)} victorias y {len(pierden)} derrotas", "habito"))

    # 5. Dónde muere a contra b.
    muertes = [m for r in registros for m in r["muertes"] if m[1]]
    if len(muertes) >= MIN_PELEAS:
        zonas = Counter(nombre_zona(m[2:]) for m in muertes)
        zona, veces = zonas.most_common(1)[0]
        # Que un jugador de línea muera en su línea no dice nada.
        propia = {"TOP": "la línea de top", "MIDDLE": "mid", "BOTTOM": "la línea de bot", "UTILITY": "la línea de bot"}.get(pos)
        if veces / len(muertes) >= 0.25 and zona != propia:
            datos.append(
                (
                    100 * veces / len(muertes) - 15,
                    f"El {_pct(veces, len(muertes))}% de las muertes de {nombre_a} con {nombre_b} de por medio antes del 15 son en {zona}.",
                    f"{len(muertes)} muertes",
                )
            )

    datos.sort(key=lambda d: d[0], reverse=True)
    # Lo que hacen distinto los que ganan es lo más aprovechable: al menos uno entra siempre.
    elegidos = datos[:4]
    habito = next((d for d in datos if len(d) > 3), None)
    if habito and habito not in elegidos:
        elegidos[-1] = habito

    # Build: lo más jugado en este duelo y cómo le va. Va aparte y en pequeño.
    build = None
    runas = Counter(tuple(r["runa"]) for r in registros if r.get("runa"))
    objetos = Counter(r["item"][0] for r in registros if r.get("item"))
    habs = Counter(r["hab"].split(">")[1] for r in registros if r.get("hab"))
    if runas and objetos:
        runa = runas.most_common(1)[0][0]
        obj = objetos.most_common(1)[0][0]
        con_obj = [r for r in registros if r.get("item") and r["item"][0] == obj]
        build = {
            "runa": nombre_runa(runa[0]),
            "secundaria": nombre_runa(runa[1]),
            "objeto": nombre_objeto(obj),
            "minuto": _num(statistics.median(r["item"][1] for r in con_obj)),
            "wr_objeto": _pct(sum(r["g"] for r in con_obj), len(con_obj)),
            "n_objeto": len(con_obj),
            "maximiza": " > ".join(habs.most_common(1)[0][0]) if habs else "",
        }

    return {
        "n": n,
        "wr": _pct(len(ganan), n),
        "datos": [{"texto": d[1], "detalle": d[2]} for d in elegidos],
        "build": build,
        "poco": False,
    }


def metricas(pos):
    """Lo que se compara entre tú y tu referencia: (nombre, función del registro, decimales, con signo)."""
    filas = [
        ("Muertes antes del 10", lambda r: r["m10"], 1, False),
        ("Peleas con tu rival antes del 6", lambda r: sum(1 for p in r["peleas"] if p[1] < 6), 1, False),
    ]
    if pos == "JUNGLE":
        filas.append(("CS al 10", lambda r: r["cs10"], 0, False))
    elif pos != "UTILITY":
        filas.append(("CS sobre tu rival al 10", lambda r: (r["dif"].get("10") or [None] * 3)[2], 0, True))
    filas.append(("Oro sobre tu rival al 10", lambda r: (r["dif"].get("10") or [None])[0], 0, True))
    return filas


def comparar(mios, referencia, pos, nombre_ref, minimo=MIN_GRUPO):
    """Tus medias al lado de las de tu referencia (los que ganan el duelo, Challenger, un jugador...).

    Con una sola partida tuya sirve para la revisión: tu partida contra lo que hace tu referencia.
    """
    if not mios or len(referencia) < minimo:
        return None
    filas = []
    for nombre, fn, dec, con_signo in metricas(pos):
        t, g = _media(fn(r) for r in mios), _media(fn(r) for r in referencia)
        if t is not None and g is not None:
            fmt = (lambda x: f"{x:+.0f}") if con_signo else (lambda x, d=dec: _num(x, d))
            filas.append({"que": nombre, "tu": fmt(t), "ref": fmt(g), "mejor": _mejor(nombre, t, g)})
    return {"n": len(mios), "n_ref": len(referencia), "ref": nombre_ref, "filas": filas}


def _mejor(nombre, tu, ref):
    """Si tu número es mejor (True), peor (False) o parecido (None) que el de tu referencia."""
    if nombre.startswith("Muertes"):
        dif = ref - tu
    elif nombre.startswith("Peleas"):
        return None  # pelear más o menos no es mejor ni peor por sí mismo
    else:
        dif = tu - ref
    margen = 0.25 if nombre.startswith("Muertes") else (5 if "CS" in nombre else 150)
    return None if abs(dif) < margen else dif > 0
