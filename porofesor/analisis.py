"""Cálculos sobre partidas y líneas de tiempo. Funciones puras: no tocan red ni disco."""
import itertools
import statistics
from collections import Counter

COLAS_GRIETA = {400, 420, 430, 440, 480, 490}
POSICIONES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
NOMBRE_POS = {"TOP": "top", "JUNGLE": "jungla", "MIDDLE": "mid", "BOTTOM": "ADC", "UTILITY": "support"}
NOMBRE_LINEA = {"top": "top", "mid": "mid", "bot": "bot"}
SMITE = 11
MIN = 60000
CAMPO_LINEA = "laningPhaseGoldExpAdvantage"
# Kills en solitario por partida a partir de las cuales un jugador destaca en su rol
# (medido en Diamante-Master: la mediana es 2 en top y mid, 1 en jungla, 0 en bot).
UMBRAL_SOLO = {"TOP": 3.5, "MIDDLE": 3.5, "JUNGLE": 2.5, "BOTTOM": 2.5, "UTILITY": 1.5}
# Suma de maestría de todos los campeones por debajo de la cual la cuenta se considera recién hecha.
MAESTRIA_CUENTA_NUEVA = 200000
# Muertes antes del 15 de un jugador normal en esas partidas.
MUERTES15_NORMAL = 3.0

# Campos de "challenges" que se conservan de cada jugador al guardar una partida.
CH_CAMPOS = (
    "laningPhaseGoldExpAdvantage",
    "earlyLaningPhaseGoldExpAdvantage",
    "maxCsAdvantageOnLaneOpponent",
    "soloKills",
    "killParticipation",
    "teamDamagePercentage",
    "takedownsFirstXMinutes",
    "killsOnLanersEarlyJungleAsJungler",
    "junglerKillsEarlyJungle",
    "enemyJungleMonsterKills",
    "jungleCsBefore10Minutes",
    "initialBuffCount",
    "initialCrabCount",
    "scuttleCrabKills",
    "earliestDragonTakedown",
    "dragonTakedowns",
    "voidMonsterKill",
    "riftHeraldTakedowns",
    "baronTakedowns",
    "epicMonsterSteals",
    "buffsStolen",
)


# --- reducción de las respuestas de Riot ---------------------------------------------
def reducir_partida(m):
    """Se queda con lo que usa el panel (una partida completa pesa ~80 KB)."""
    info = m["info"]
    duracion = info.get("gameDuration", 0)
    jug = []
    for p in info["participants"]:
        ch = p.get("challenges") or {}
        jug.append(
            {
                "puuid": p.get("puuid", ""),
                "nombre": p.get("riotIdGameName") or p.get("summonerName", ""),
                "tag": p.get("riotIdTagline", ""),
                "pid": p["participantId"],
                "equipo": p["teamId"],
                "campeon": p["championId"],
                "pos": p.get("teamPosition") or "",
                "gana": bool(p.get("win")),
                "k": p.get("kills", 0),
                "d": p.get("deaths", 0),
                "a": p.get("assists", 0),
                "cs": p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
                "oro": p.get("goldEarned", 0),
                "dano": p.get("totalDamageDealtToChampions", 0),
                "vision": p.get("visionScore", 0),
                "wards": p.get("wardsPlaced", 0),
                "control": p.get("visionWardsBoughtInGame", 0),
                "s1": p.get("summoner1Id", 0),
                "s2": p.get("summoner2Id", 0),
                "ch": {k: round(ch[k], 3) for k in CH_CAMPOS if isinstance(ch.get(k), (int, float))},
            }
        )
    equipos = {}
    for t in info.get("teams", []):
        obj = t.get("objectives", {})
        equipos[str(t["teamId"])] = {
            "gana": bool(t.get("win")),
            "obj": {k: [bool(v.get("first")), v.get("kills", 0)] for k, v in obj.items()},
        }
    remake = duracion < 300 or any(p.get("gameEndedInEarlySurrender") for p in info["participants"])
    return {
        "id": m["metadata"]["matchId"],
        "creacion": info.get("gameCreation", 0),
        "duracion": duracion,
        "cola": info.get("queueId", 0),
        "mapa": info.get("mapId", 0),
        "remake": bool(remake),
        "equipos": equipos,
        "jug": jug,
    }


def reducir_linea(t):
    """De la línea de tiempo (~850 KB) guarda posiciones y oro por minuto hasta el 15, kills y monstruos."""
    info = t["info"]
    pos, est = {}, {}
    for f in info["frames"][:16]:
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
            if e["type"] == "CHAMPION_KILL" and e["timestamp"] < 20 * MIN:
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
                    ]
                )
    return {
        "id": t["metadata"]["matchId"],
        "pids": {p["puuid"]: p["participantId"] for p in info.get("participants", [])},
        "pos": pos,
        "est": est,
        "kills": kills,
        "monstruos": monstruos,
    }


# --- utilidades ------------------------------------------------------------------------
def num(x, decimales=1):
    return f"{x:.{decimales}f}".replace(".", ",")


def mmss(ms):
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def media(valores):
    valores = list(valores)
    return sum(valores) / len(valores) if valores else 0.0


def jugador_en(partida, puuid):
    for j in partida["jug"]:
        if j["puuid"] == puuid:
            return j
    return None


def validas(partidas):
    """Partidas de la Grieta que no son remake."""
    return [m for m in partidas if not m["remake"] and m["cola"] in COLAS_GRIETA]


def equipo_de_pid(pid):
    return 100 if int(pid) <= 5 else 200


# La Grieta es simétrica respecto al centro: lo que pasa en un lado se lleva al otro con esto.
SUMA_X, SUMA_Y = 14740, 14820
# Minutos del mapa de posiciones del jungla rival (primer clear y primeros movimientos).
MAPA_MINUTOS = (2, 3, 4, 5, 6)


def espejo(x, y):
    return SUMA_X - x, SUMA_Y - y


def mapa_posiciones(con_linea, equipo_ahora):
    """{minuto: [[x, y], ...]} de un jugador en sus partidas, todas llevadas al lado del mapa que le toca hoy."""
    mapa = {}
    for _, j, l in con_linea:
        pos = l["pos"].get(str(j["pid"])) or []
        girar = equipo_de_pid(j["pid"]) != equipo_ahora
        for m in MAPA_MINUTOS:
            if len(pos) > m and any(pos[m]):
                x, y = espejo(*pos[m]) if girar else pos[m]
                mapa.setdefault(str(m), []).append([x, y])
    return mapa


# --- geografía del mapa ------------------------------------------------------------------
# Coordenadas de 0 a ~15000; base azul abajo a la izquierda, base roja arriba a la derecha.
_R2 = 2**0.5


def _diagonales(x, y):
    """Distancia con signo a la línea de mid (positivo = lado superior) y al río (positivo = mitad roja)."""
    return (y - x) / _R2, (x + y - 14900) / _R2


def _en_base(x, y):
    return (x < 3800 and y < 3800) or (x > 11000 and y > 11000)


def zona(x, y):
    """Devuelve (tipo, lado, mitad): tipo base/top/mid/bot/rio/jungla, lado 'sup'/'inf', mitad 100/200."""
    d_mid, d_rio = _diagonales(x, y)
    lado = "sup" if d_mid > 0 else "inf"
    mitad = 100 if d_rio < 0 else 200
    if _en_base(x, y):
        tipo = "base"
    elif (x < 2300 and y > 3800) or (y > 12500 and x < 11000):
        tipo = "top"
    elif (y < 2300 and x > 3800) or (x > 12500 and y < 11000):
        tipo = "bot"
    elif abs(d_mid) < 1000:
        tipo = "mid"
    elif abs(d_rio) < 900:
        tipo = "rio"
    else:
        tipo = "jungla"
    return tipo, lado, mitad


def linea_de_kill(x, y):
    """Línea a la que pertenece una kill, con bandas más anchas que zona() porque los ganks acaban fuera de la calle."""
    d_mid, _ = _diagonales(x, y)
    if _en_base(x, y):
        return "base"
    if (x < 3300 and y > 5000) or (y > 11500 and x < 9800):
        return "top"
    if (y < 3300 and x > 5000) or (x > 11500 and y < 9800):
        return "bot"
    if abs(d_mid) < 1600:
        return "mid"
    return "jungla"


def lado_del_buff(buff, equipo):
    """En qué lado del mapa cae cada buff según el equipo: el azul del equipo azul está arriba, el del rojo abajo."""
    arriba = (buff == "azul") == (equipo == 100)
    return "sup" if arriba else "inf"


def inicio_jungla(linea, pid):
    """Buff por el que empieza el jungla ('rojo', 'azul'), 'invade' o None si no se puede saber.

    Al 1:00 el jungla está parado en su primer campo; al 2:00 ya va por el tercero y
    cruzando mid, así que ese minuto solo sirve de respaldo.
    """
    equipo = equipo_de_pid(pid)
    pos = linea["pos"].get(str(pid)) or []
    for minuto in (1, 2):
        if len(pos) <= minuto:
            continue
        tipo, lado, mitad = zona(*pos[minuto])
        if tipo != "jungla":
            continue
        if mitad != equipo:
            return "invade"
        return "azul" if lado == lado_del_buff("azul", equipo) else "rojo"
    return None


def lado_al(linea, pid, minuto):
    """Lado del mapa ('sup'/'inf') en el que está el jugador en ese minuto, o None si está en base."""
    pos = linea["pos"].get(str(pid)) or []
    if len(pos) <= minuto:
        return None
    tipo, lado, _ = zona(*pos[minuto])
    return None if tipo == "base" else lado


def primer_gank(linea, pid):
    """(ms, línea) de la primera kill o asistencia del jugador en una línea antes del minuto 10."""
    pid = int(pid)
    for t, x, y, asesino, _victima, asistentes in linea["kills"]:
        if t >= 10 * MIN:
            break
        if pid != asesino and pid not in asistentes:
            continue
        donde = linea_de_kill(x, y)
        if donde in NOMBRE_LINEA:
            return t, donde
    return None


def muertes_antes(linea, pid, minuto):
    pid = int(pid)
    return sum(1 for k in linea["kills"] if k[4] == pid and k[0] < minuto * MIN)


def oro_al(linea, pid, minuto):
    est = linea["est"].get(str(pid)) or []
    return est[minuto][0] if len(est) > minuto else None


# --- roles en la partida en vivo ----------------------------------------------------------
def asignar_roles(equipo, roles_campeon, historiales=None):
    """Reparte las cinco posiciones entre los cinco jugadores de un equipo.

    equipo: lista de dicts con 'campeon', 's1', 's2' y 'puuid'.
    roles_campeon: {campeon: {posición: frecuencia}}.
    historiales: {puuid: Counter de posiciones recientes} (opcional, afina el reparto).
    Devuelve una lista de posiciones en el mismo orden que 'equipo'.
    """
    if len(equipo) != 5:
        return [""] * len(equipo)
    historiales = historiales or {}

    def puntos(j, pos):
        tasas = roles_campeon.get(j["campeon"]) or {}
        total = sum(tasas.values())
        s = tasas.get(pos, 0) / total if total else 0.2
        if pos == "JUNGLE":
            s += 2.0 if SMITE in (j.get("s1"), j.get("s2")) else -2.0
        hist = historiales.get(j.get("puuid"))
        if hist:
            jugadas = sum(hist.values())
            if jugadas:
                s += 0.6 * hist.get(pos, 0) / jugadas
        return s

    tabla = [[puntos(j, pos) for pos in POSICIONES] for j in equipo]
    mejor = max(itertools.permutations(range(5)), key=lambda perm: sum(tabla[i][perm[i]] for i in range(5)))
    return [POSICIONES[mejor[i]] for i in range(5)]


def rival_probable(rivales, pos, roles_campeon):
    """En la selección no se ven las posiciones rivales: el que más se juega en esa posición.

    Con los cinco elegidos se reparten las posiciones entre todos; con menos, gana el más típico de la
    posición si al menos un 30% de sus partidas son ahí.
    """
    if not rivales or not pos:
        return None
    if len(rivales) == 5:
        reparto = asignar_roles([{"campeon": c} for c in rivales], roles_campeon)
        return next((c for c, p in zip(rivales, reparto) if p == pos), None)

    def cuota(c):
        tasas = roles_campeon.get(c) or {}
        total = sum(tasas.values())
        return tasas.get(pos, 0) / total if total else 0

    mejor = max(rivales, key=cuota)
    return mejor if cuota(mejor) >= 0.3 else None


# --- resumen de un jugador ------------------------------------------------------------------
def resumen_jugador(puuid, partidas, campeon, lineas=None):
    """Estadísticas de un jugador sobre su muestra de partidas recientes (la más reciente primero)."""
    lineas = lineas or {}
    juegos = [(m, jugador_en(m, puuid)) for m in validas(partidas)]
    juegos = [(m, j) for m, j in juegos if j]
    n = len(juegos)
    res = {"n": n, "v": sum(1 for _, j in juegos if j["gana"]), "racha": [j["gana"] for _, j in juegos[:10]]}
    racha = 0
    for _, j in juegos:
        if j["gana"] != juegos[0][1]["gana"]:
            break
        racha += 1 if j["gana"] else -1
    res["racha_actual"] = racha

    con = [j for _, j in juegos if j["campeon"] == campeon]
    res["camp"] = {
        "n": len(con),
        "v": sum(1 for j in con if j["gana"]),
        "kda": [media(j[c] for j in con) for c in ("k", "d", "a")] if con else None,
    }
    res["roles"] = dict(Counter(j["pos"] for _, j in juegos if j["pos"]))
    res["kda"] = [media(j[c] for _, j in juegos) for c in ("k", "d", "a")] if n else None

    def ch(campo, lista=None):
        return [j["ch"][campo] for _, j in (lista or juegos) if campo in j["ch"]]

    # Riot solo marca la ventaja de línea cuando es clara (~15% de las partidas), así que
    # "perder línea" se lee en la marca del rival directo.
    linea = {"n": 0, "v": 0, "d": 0}
    for m, j in juegos:
        rival = next((r for r in m["jug"] if r["pos"] == j["pos"] and r["equipo"] != j["equipo"]), None)
        if not j["pos"] or not rival or CAMPO_LINEA not in j["ch"]:
            continue
        linea["n"] += 1
        linea["v"] += int(j["ch"][CAMPO_LINEA] >= 1)
        linea["d"] += int(rival["ch"].get(CAMPO_LINEA, 0) >= 1)
    res["linea"] = linea
    res["solo"] = media(ch("soloKills"))
    res["kp"] = media(ch("killParticipation"))
    res["dano_pct"] = media(ch("teamDamagePercentage"))
    res["ultima"] = juegos[0][0]["creacion"] if juegos else 0

    tempranas = []
    for m, j in juegos:
        linea = lineas.get(m["id"])
        if linea:
            tempranas.append(muertes_antes(linea, j["pid"], 15))
    res["muertes15"] = {"n": len(tempranas), "media": media(tempranas)}
    return res


def rol_principal(res):
    roles = res.get("roles") or {}
    return max(roles, key=roles.get) if roles else ""


def fuera_de_rol(res, rol):
    """Con muestra suficiente, el rol de hoy aparece en menos del 15% de sus partidas."""
    roles = res.get("roles") or {}
    total = sum(roles.values())
    return bool(rol) and total >= 8 and roles.get(rol, 0) / total < 0.15


def etiquetas(res, rol, maestria, ahora_ms):
    """Etiquetas cortas del jugador. tono: 'fuerte', 'flojo' o 'neutro' (sobre el jugador, no sobre ti)."""
    out = []
    n = res["n"]
    camp = res["camp"]
    puntos = (maestria or {}).get("championPoints")
    ultimo_uso = (maestria or {}).get("lastPlayTime")
    total = (maestria or {}).get("total")
    # Con poca maestría en toda la cuenta, que tenga poca en este campeón no dice nada.
    cuenta_nueva = total is not None and total < MAESTRIA_CUENTA_NUEVA

    if n >= 8 and camp["n"] / n >= 0.6:
        out.append({"t": "OTP", "tono": "fuerte", "d": f"{camp['n']} de sus últimas {n} con este campeón"})
    elif puntos is not None and puntos >= 300000:
        out.append({"t": "Main", "tono": "fuerte", "d": f"{puntos // 1000}k de maestría"})
    if cuenta_nueva:
        out.append({"t": "Cuenta nueva", "tono": "neutro", "d": f"{total // 1000}k de maestría entre todos sus campeones: posible cuenta secundaria"})
    elif puntos is not None and puntos < 5000 and camp["n"] <= 1:
        out.append({"t": "Primera vez", "tono": "flojo", "d": f"{puntos} puntos de maestría"})
    elif puntos is not None and puntos < 25000 and camp["n"] <= 2:
        out.append({"t": "Poco rodado", "tono": "flojo", "d": f"{puntos // 1000}k de maestría"})
    if ultimo_uso and puntos and puntos >= 25000:
        dias = (ahora_ms - ultimo_uso) / 86400000
        if dias >= 30:
            out.append({"t": "Oxidado", "tono": "flojo", "d": f"{int(dias)} días sin jugarlo"})
    if fuera_de_rol(res, rol):
        principal = NOMBRE_POS.get(rol_principal(res), "?")
        out.append({"t": "Fuera de rol", "tono": "flojo", "d": f"suele jugar {principal}"})
    if res["racha_actual"] >= 3:
        out.append({"t": f"Racha +{res['racha_actual']}", "tono": "fuerte", "d": "victorias seguidas"})
    elif res["racha_actual"] <= -3:
        out.append({"t": f"Racha {res['racha_actual']}", "tono": "flojo", "d": "derrotas seguidas"})
    linea = res["linea"]
    if rol != "JUNGLE" and linea["n"] >= 5:
        if linea["v"] / linea["n"] >= 0.4 and linea["v"] > linea["d"]:
            out.append({"t": "Gana línea", "tono": "fuerte", "d": f"saca ventaja clara en {linea['v']} de {linea['n']}"})
        elif linea["d"] / linea["n"] >= 0.4 and linea["d"] > linea["v"]:
            out.append({"t": "Pierde línea", "tono": "flojo", "d": f"le sacan ventaja clara en {linea['d']} de {linea['n']}"})
    m15 = res["muertes15"]
    if m15["n"] >= 3 and m15["media"] >= MUERTES15_NORMAL + 1.5:
        out.append({"t": "Muere pronto", "tono": "flojo", "d": f"{num(m15['media'])} muertes antes del 15"})
    return out


def premades(equipo, muestras):
    """Parejas o grupos que vienen juntos: comparten equipo en 2 o más partidas recientes.

    equipo: lista de puuids del mismo equipo. muestras: {puuid: [partidas]}.
    Devuelve {puuid: número de grupo}.
    """
    juntos = Counter()
    vistas = set()
    for puuid in equipo:
        for m in muestras.get(puuid, []):
            if m["id"] in vistas:
                continue
            vistas.add(m["id"])
            por_equipo = {}
            for j in m["jug"]:
                if j["puuid"] in equipo:
                    por_equipo.setdefault(j["equipo"], []).append(j["puuid"])
            for grupo in por_equipo.values():
                for a, b in itertools.combinations(sorted(grupo), 2):
                    juntos[(a, b)] += 1
    padre = {p: p for p in equipo}

    def raiz(p):
        while padre[p] != p:
            p = padre[p]
        return p

    for (a, b), veces in juntos.items():
        if veces >= 2:
            padre[raiz(a)] = raiz(b)
    grupos = {}
    for p in equipo:
        grupos.setdefault(raiz(p), []).append(p)
    out = {}
    for i, miembros in enumerate(g for g in grupos.values() if len(g) > 1):
        for p in miembros:
            out[p] = i + 1
    return out


# --- perfil del jungla rival ---------------------------------------------------------------
def perfil_jungla(puuid, partidas, lineas, campeon, equipo_ahora):
    """Tendencias de un jungla a partir de sus partidas de jungla y de sus líneas de tiempo.

    Devuelve datos crudos y 'tarjetas' ya redactadas para el panel.
    'tono' va desde tu punto de vista: 'ojo' es algo de lo que cuidarte, 'bien' algo que te favorece.
    """
    juegos = [(m, jugador_en(m, puuid)) for m in validas(partidas)]
    juegos = [(m, j) for m, j in juegos if j and j["pos"] == "JUNGLE"]
    con_campeon = [(m, j) for m, j in juegos if j["campeon"] == campeon]
    con_linea = [(m, j, lineas[m["id"]]) for m, j in juegos if m["id"] in lineas]
    perfil = {
        "n": len(juegos),
        "n_campeon": len(con_campeon),
        "n_lineas": len(con_linea),
        "tarjetas": [],
        "ganks": {},
        "snowball": None,
    }
    tarjetas = perfil["tarjetas"]
    if not juegos:
        return perfil
    perfil["mapa"] = mapa_posiciones(con_linea, equipo_ahora)

    # Inicio del primer clear.
    inicios = Counter()
    cruza = []  # ¿al 3:00 está en el lado contrario al de su primer buff?
    for _, j, l in con_linea:
        buff = inicio_jungla(l, j["pid"])
        if not buff:
            continue
        inicios[buff] += 1
        al_tres = lado_al(l, j["pid"], 3)
        if buff != "invade" and al_tres:
            cruza.append(al_tres != lado_del_buff(buff, equipo_de_pid(j["pid"])))
    total_inicios = sum(inicios.values())
    buff, veces = max(((b, inicios[b]) for b in ("rojo", "azul")), key=lambda x: x[1])
    if total_inicios >= 2 and veces:
        lado = lado_del_buff(buff, equipo_ahora)
        nombre = {"sup": "superior", "inf": "inferior"}
        marcado = veces / total_inicios >= 0.7
        detalle = f"Hoy su {buff} cae en el lado {nombre[lado]}."
        if len(cruza) >= 2:
            if sum(cruza) / len(cruza) >= 0.6:
                otro = "inf" if lado == "sup" else "sup"
                detalle += f" Al 3:00 ya ha cruzado al lado {nombre[otro]} en {sum(cruza)} de {len(cruza)}."
            else:
                detalle += f" Al 3:00 sigue en el lado de su primer buff en {len(cruza) - sum(cruza)} de {len(cruza)}."
        if inicios["invade"]:
            detalle += f" Empezó en jungla rival en {inicios['invade']}."
        tarjetas.append(
            {
                "titulo": "Inicio",
                "valor": f"{buff.capitalize()} en {veces} de {total_inicios}",
                "detalle": detalle if marcado else "Sin patrón claro. " + detalle,
                "tono": "neutro",
            }
        )
        perfil["inicio"] = {"buff": buff, "veces": veces, "n": total_inicios, "lado": lado, "marcado": marcado}

    # Primer gank con premio.
    ganks = [g for g in (primer_gank(l, j["pid"]) for _, j, l in con_linea) if g]
    if con_linea:
        por_linea = Counter(g[1] for g in ganks)
        perfil["ganks"] = dict(por_linea)
        if ganks:
            mediana = statistics.median(g[0] for g in ganks)
            reparto = " · ".join(f"{l} {por_linea[l]}" for l in ("top", "mid", "bot") if por_linea[l])
            tarjetas.append(
                {
                    "titulo": "Primer gank",
                    "valor": f"min {mmss(mediana)} · {reparto}",
                    "detalle": f"Primera kill o asistencia en una línea antes del 10, en {len(ganks)} de "
                    f"{len(con_linea)} partidas.",
                    "tono": "ojo" if mediana < 4.5 * MIN else "neutro",
                }
            )
        else:
            tarjetas.append(
                {
                    "titulo": "Primer gank",
                    "valor": "Ninguno antes del 10",
                    "detalle": f"En {len(con_linea)} partidas no sacó kill ni asistencia en línea antes del 10.",
                    "tono": "bien",
                }
            )

    # Dónde pasa el early y cuánto pisa la jungla contraria.
    lados = Counter()
    pisa = 0
    for _, j, l in con_linea:
        equipo = equipo_de_pid(j["pid"])
        pos = l["pos"].get(str(j["pid"])) or []
        dentro = False
        for minuto, (x, y) in enumerate(pos):
            tipo, lado, mitad = zona(x, y)
            if 3 <= minuto <= 8 and tipo != "base":
                lados[lado] += 1
            if 2 <= minuto <= 7 and tipo == "jungla" and mitad != equipo:
                dentro = True
        pisa += dentro
    if sum(lados.values()) >= 10:
        lado, veces = lados.most_common(1)[0]
        pct = round(100 * veces / sum(lados.values()))
        if pct >= 58:
            nombre = "superior (top y larvas)" if lado == "sup" else "inferior (bot y dragón)"
            tarjetas.append(
                {
                    "titulo": "Lado del early",
                    "valor": f"{pct}% en el lado {nombre.split(' ')[0]}",
                    "detalle": f"Del minuto 3 al 8 suele estar en el lado {nombre}.",
                    "tono": "neutro",
                }
            )
    if con_linea:
        # En Diamante-Master la mediana es de 10 monstruos rivales por partida y el cuartil alto, 18.
        robados = media(j["ch"].get("enemyJungleMonsterKills", 0) for _, j in juegos)
        pronto = pisa / len(con_linea)
        tarjetas.append(
            {
                "titulo": "Invades",
                "valor": f"Roba {num(robados)} monstruos por partida",
                "detalle": f"Pisa la jungla rival antes del 8 en {pisa} de {len(con_linea)}. Referencia en Diamante-Master: 10 por partida.",
                "tono": "ojo" if robados >= 18 or pronto >= 0.5 else ("bien" if robados <= 5 and pisa == 0 else "neutro"),
            }
        )
        perfil["invade"] = {"veces": pisa, "n": len(con_linea), "robados": robados}

    # Objetivos.
    primer_dragon = [j["ch"]["earliestDragonTakedown"] for _, j in juegos if j["ch"].get("earliestDragonTakedown")]
    primero = sum(1 for m, j in juegos if (m["equipos"].get(str(j["equipo"]), {}).get("obj", {}).get("dragon") or [0])[0])
    larvas = media(j["ch"].get("voidMonsterKill", 0) for _, j in juegos)
    valor = f"Primer dragón en {primero} de {len(juegos)}"
    if primer_dragon:
        valor += f" (min {mmss(statistics.median(primer_dragon) * 1000)})"
    tarjetas.append(
        {
            "titulo": "Objetivos",
            "valor": valor,
            "detalle": f"Larvas: {num(larvas)} por partida.",
            "tono": "ojo" if primero / len(juegos) >= 0.65 else "neutro",
        }
    )

    # Qué pasa cuando se adelanta.
    delante, detras = [], []
    for m, j, l in con_linea:
        rival = next((r for r in m["jug"] if r["pos"] == "JUNGLE" and r["equipo"] != j["equipo"]), None)
        if not rival:
            continue
        mio, suyo = oro_al(l, j["pid"], 10), oro_al(l, rival["pid"], 10)
        if mio is None or suyo is None:
            continue
        if mio - suyo >= 300:
            delante.append(j["gana"])
        elif suyo - mio >= 300:
            detras.append(j["gana"])
    base = con_campeon if len(con_campeon) >= 3 else juegos
    k, d, a = (media(j[c] for _, j in base) for c in ("k", "d", "a"))
    con_que = "con este campeón" if base is con_campeon else "de jungla"
    dano = media(j["ch"].get("teamDamagePercentage", 0) for _, j in base)
    perfil["snowball"] = {
        "delante": [sum(delante), len(delante)],
        "detras": [sum(detras), len(detras)],
        "kda": [k, d, a],
        "dano_pct": dano,
        "solo": media(j["ch"].get("soloKills", 0) for _, j in base),
    }
    if delante or detras:
        partes = []
        if delante:
            partes.append(f"por delante al 10 gana {sum(delante)} de {len(delante)}")
        if detras:
            partes.append(f"por detrás {sum(detras)} de {len(detras)}")
        peligro = len(delante) >= 3 and sum(delante) / len(delante) >= 0.75
        tarjetas.append(
            {
                "titulo": "Si se adelanta",
                "valor": "; ".join(partes).capitalize(),
                "detalle": f"{num(k)}/{num(d)}/{num(a)} de media {con_que}, {round(dano * 100)}% del daño de su equipo.",
                "tono": "ojo" if peligro else "neutro",
            }
        )
    else:
        tarjetas.append(
            {
                "titulo": "Rendimiento",
                "valor": f"{num(k)}/{num(d)}/{num(a)} de media {con_que}",
                "detalle": f"{round(dano * 100)}% del daño de su equipo.",
                "tono": "neutro",
            }
        )

    tempranas = [muertes_antes(l, j["pid"], 10) for _, j, l in con_linea]
    if tempranas:
        m10 = media(tempranas)
        tarjetas.append(
            {
                "titulo": "Muertes tempranas",
                "valor": f"{num(m10)} antes del 10",
                "detalle": f"Media de {len(tempranas)} partidas con línea de tiempo.",
                "tono": "bien" if m10 >= 2 else "neutro",
            }
        )
    return perfil


# --- dónde va a haber errores -----------------------------------------------------------------
def fuerza(res, rol, primera_vez=False):
    """Puntuación de lo sólido que es un jugador en su línea; 0 es normal, positivo es fuerte.

    Devuelve (puntuación, motivos) con frases cortas que explican la nota.
    """
    s = 0.0
    motivos = []
    linea = res["linea"]
    if linea["n"] >= 4:
        s += (linea["v"] - linea["d"]) / linea["n"] * 1.5
        if linea["d"] / linea["n"] >= 0.4 and linea["d"] > linea["v"]:
            motivos.append(f"le sacan ventaja clara de línea en {linea['d']} de {linea['n']}")
        elif linea["v"] / linea["n"] >= 0.4 and linea["v"] > linea["d"]:
            motivos.append(f"saca ventaja clara de línea en {linea['v']} de {linea['n']}")
    m15 = res["muertes15"]
    if m15["n"] >= 2:
        s += (MUERTES15_NORMAL - m15["media"]) * 0.3
        if m15["media"] >= MUERTES15_NORMAL + 1:
            motivos.append(f"muere {num(m15['media'])} veces antes del 15")
        elif m15["media"] <= MUERTES15_NORMAL - 1.5:
            motivos.append(f"apenas muere antes del 15 ({num(m15['media'])})")
    if res["n"] >= 6:
        s += (res["v"] / res["n"] - 0.5)
    if res["racha_actual"] <= -3:
        s -= 0.2
        motivos.append(f"lleva {-res['racha_actual']} derrotas seguidas")
    if fuera_de_rol(res, rol):
        s -= 0.4
        motivos.append("va fuera de rol")
    if primera_vez:
        s -= 0.4
        motivos.append("casi no ha jugado este campeón")
    return s, motivos


def lineas_de_juego(aliados, rivales):
    """Ordena top, mid y bot por lo que promete el rival de esa línea a fallar.

    aliados/rivales: {posición: {"nombre", "campeon", "res", "primera_vez"}}.
    """
    grupos = {"top": ("TOP",), "mid": ("MIDDLE",), "bot": ("BOTTOM", "UTILITY")}
    out = []
    for linea, posiciones in grupos.items():
        lado = {}
        for clave, equipo in (("aliado", aliados), ("rival", rivales)):
            notas, motivos, hay_datos = [], [], False
            for pos in posiciones:
                j = equipo.get(pos)
                if not j or not j.get("res") or not j["res"]["n"]:
                    continue
                hay_datos = True
                s, m = fuerza(j["res"], pos, j.get("primera_vez"))
                notas.append(s)
                motivos += [f"{j['campeon']} {x}" for x in m]
            lado[clave] = {"nota": media(notas), "motivos": motivos, "datos": hay_datos}
        if not lado["rival"]["datos"]:
            continue
        diferencia = lado["aliado"]["nota"] - lado["rival"]["nota"]
        if lado["rival"]["nota"] <= -0.45:
            veredicto, tono = "Aquí se equivocan", "bien"
        elif diferencia <= -0.6:
            veredicto, tono = "Aquí sufre tu equipo", "ojo"
        elif diferencia >= 0.6:
            veredicto, tono = "Tu línea es mejor", "bien"
        else:
            veredicto, tono = "Igualada", "neutro"
        out.append(
            {
                "linea": linea,
                "veredicto": veredicto,
                "tono": tono,
                "debilidad": -lado["rival"]["nota"],
                "diferencia": diferencia,
                "rival": lado["rival"]["motivos"],
                "aliado": lado["aliado"]["motivos"],
            }
        )
    out.sort(key=lambda x: x["debilidad"], reverse=True)
    return out


# --- historial propio ----------------------------------------------------------------------
def mi_historial(mis_puuids, mis_partidas, mi_campeon, rivales, presentes, ahora_ms, mi_pos=""):
    """Qué dice tu propio historial de esta partida.

    mi_pos: tu posición; el rival de esa posición es tu duelo directo (vs_directo).

    mis_partidas: partidas clasificatorias propias de la temporada (más reciente primero).
    rivales: lista de {"campeon", "pos", "nombre_campeon"}.
    presentes: {puuid: nombre visible} de los otros nueve jugadores de la partida.
    """
    juegos = []
    for m in validas(mis_partidas):
        yo = next((j for j in m["jug"] if j["puuid"] in mis_puuids), None)
        if yo:
            juegos.append((m, yo))
    out = {"n": len(juegos), "campeon": None, "vs": [], "vs_directo": None, "conocidos": []}
    if not juegos:
        return out

    con = [(m, yo) for m, yo in juegos if yo["campeon"] == mi_campeon]
    out["campeon"] = {
        "n": len(con),
        "v": sum(1 for _, yo in con if yo["gana"]),
        "racha": [yo["gana"] for _, yo in con[:10]],
    }

    for r in rivales:
        contra = [(m, yo) for m, yo in juegos if any(j["campeon"] == r["campeon"] and j["equipo"] != yo["equipo"] for j in m["jug"])]
        mio = [(m, yo) for m, yo in contra if yo["campeon"] == mi_campeon]
        fila = {
            "campeon": r["campeon"],
            "nombre": r["nombre_campeon"],
            "pos": r["pos"],
            "n": len(contra),
            "v": sum(1 for _, yo in contra if yo["gana"]),
            "n_mio": len(mio),
            "v_mio": sum(1 for _, yo in mio if yo["gana"]),
        }
        out["vs"].append(fila)
        if mi_pos and r["pos"] == mi_pos:
            # Solo cuentan las partidas en las que los dos ibais en esa posición.
            duelo = [
                (m, yo)
                for m, yo in contra
                if yo["pos"] == mi_pos
                and any(j["campeon"] == r["campeon"] and j["pos"] == mi_pos and j["equipo"] != yo["equipo"] for j in m["jug"])
            ]
            duelo_mio = [(m, yo) for m, yo in duelo if yo["campeon"] == mi_campeon]
            out["vs_directo"] = {
                "nombre": r["nombre_campeon"],
                "pos": NOMBRE_POS.get(mi_pos, ""),
                "n": len(duelo),
                "v": sum(1 for _, yo in duelo if yo["gana"]),
                "n_mio": len(duelo_mio),
                "v_mio": sum(1 for _, yo in duelo_mio if yo["gana"]),
            }
    out["vs"].sort(key=lambda f: (f["n"] == 0, (f["v"] / f["n"]) if f["n"] else 0))

    for puuid, nombre in presentes.items():
        for m, yo in juegos:
            otro = jugador_en(m, puuid)
            if otro:
                out["conocidos"].append(
                    {
                        "nombre": nombre,
                        "contigo": otro["equipo"] == yo["equipo"],
                        "ganaste": yo["gana"],
                        "dias": int((ahora_ms - m["creacion"]) / 86400000),
                        "veces": sum(1 for m2, _ in juegos if jugador_en(m2, puuid)),
                    }
                )
                break
    return out


def pool_contra(pool, pos, rival, registros, partidas, mias, minimo):
    """Tus campeones de esa posición contra el campeón rival: opciones con datos, no una elección.

    pool: [(campeón, posición)] de más a menos jugado. registros: {campeón: [registros de Master+ de ese duelo]}.
    partidas: tus partidas de la temporada. Solo se da el % de Master+ con 'minimo' partidas o más.
    """
    filas = []
    for a, p in pool:
        if p != pos:
            continue
        regs = registros.get(a) or []
        fila = {"campeon": a, "n": len(regs), "v": sum(r["g"] for r in regs), "yo_n": 0, "yo_v": 0, "vs_n": 0, "vs_v": 0}
        for m in validas(partidas):
            j = next((x for x in m["jug"] if x["puuid"] in mias), None)
            if not j or j["campeon"] != a or j["pos"] != pos:
                continue
            fila["yo_n"] += 1
            fila["yo_v"] += int(j["gana"])
            r = next((x for x in m["jug"] if x["pos"] == pos and x["equipo"] != j["equipo"]), None)
            if r and r["campeon"] == rival:
                fila["vs_n"] += 1
                fila["vs_v"] += int(j["gana"])
        fila["wr"] = round(100 * fila["v"] / fila["n"]) if fila["n"] >= minimo else None
        filas.append(fila)
    # Primero los que tienen datos de Master+ (de más a menos %), luego el resto por tus partidas.
    filas.sort(key=lambda f: (f["wr"] is not None, f["wr"] or 0, f["yo_n"]), reverse=True)
    return filas


NIVELES_ORDEN = ("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND")
DIVISIONES = {"IV": 0, "III": 1, "II": 2, "I": 3}


def valor_liga(nivel, division, lp):
    """Puntos totales en la escalera (Hierro IV 0 LP = 0), para restar LP aunque se cambie de división.
    No es un MMR: solo cuenta lo que se ve en la clasificación oficial."""
    nivel = nivel.upper()
    if nivel in ("MASTER", "GRANDMASTER", "CHALLENGER"):
        return len(NIVELES_ORDEN) * 400 + lp
    if nivel not in NIVELES_ORDEN:
        return None
    return NIVELES_ORDEN.index(nivel) * 400 + DIVISIONES.get(division, 0) * 100 + lp
