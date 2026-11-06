"""El duelo de tu campeón contra su rival directo, medido en partidas de Master+. Funciones puras.

De cada partida con línea de tiempo salen diez registros, uno por jugador, cada uno mirado desde ese
jugador ('a') contra el de su misma posición en el otro equipo ('b'). Luego, para un duelo concreto,
se buscan los datos que no son de manual: quién gana las peleas antes y después del 6, cuánto pesa ir
por delante, qué hacen distinto los que ganan, dónde se muere, si escala, y tus números al lado.
"""

import statistics
from collections import Counter
from collections.abc import Callable, Collection, Iterable
from typing import Any, NamedTuple

from . import analisis as an
from .constantes import DURACION_MINIMA_S, MIN
from .tipos import Json, Registro

POSICIONES = an.POSICIONES
# Peleas "pequeñas": las dos del duelo implicadas y como mucho cuatro jugadores en total.
MAX_IMPLICADOS = 4
FIN_PELEAS = 15 * MIN

# Mínimos para enseñar un dato: con menos, el porcentaje es ruido.
MIN_PARTIDAS = 12
MIN_PELEAS = 10
MIN_GRUPO = 8

# Un dato de un duelo: (peso, texto, detalle), y "habito" al final en lo que hacen distinto los que ganan.
Dato = tuple[float, str, str] | tuple[float, str, str, str]
Medida = Callable[[Registro], float | None]  # lo que se mide de cada registro (None si no lo tiene)


# --- extracción (de la partida y la línea de tiempo de Riot a registros pequeños) --------------------
def _zona(pos: Json, equipo: int) -> list[Any]:
    tipo, lado, mitad = an.zona(pos.get("x", 0), pos.get("y", 0))
    return [tipo, lado, mitad == equipo]


class _Eventos(NamedTuple):
    """Lo que interesa de los eventos de la línea de tiempo, sacado en un solo recorrido."""

    kills: list[tuple[Any, ...]]  # (ms, asesino, víctima, implicados, posición, {pid: nivel} en ese momento)
    compras: dict[int, list[float]]  # pid -> [primer objeto legendario, minuto]
    habilidades: dict[int, list[int]]  # pid -> habilidades (1-4) en el orden en que las sube
    monstruos: list[tuple[int, str, int]]  # (ms, tipo, equipo que lo mata)


def extraer(partida: Json, linea: Json, legendarios: Collection[int]) -> list[Registro]:
    """Diez registros (uno por jugador con rival de posición) de una partida de la Grieta.

    legendarios: ids de objetos que cuentan como primer objeto completo.
    """
    info, tl = partida["info"], linea["info"]
    jug = info["participants"]
    if info.get("gameDuration", 0) < DURACION_MINIMA_S or any(p.get("gameEndedInEarlySurrender") for p in jug):
        return []
    parejas = _parejas(jug)
    if not parejas:
        return []
    pid_equipo = {p["participantId"]: p["teamId"] for p in jug}
    frames = tl["frames"]
    eventos = _eventos(frames, jug, legendarios)
    version = ".".join(info.get("gameVersion", "").split(".")[:2])
    return [_registro(pos, a, b, info, version, frames, eventos, pid_equipo) for pos, a, b in parejas]


def _parejas(jug: list[Json]) -> list[tuple[str, Json, Json]]:
    """(posición, jugador, su rival) de cada posición con un jugador por equipo, desde los dos lados."""
    por_pos: dict[tuple[int, str], list[Json]] = {}
    for p in jug:
        por_pos.setdefault((p["teamId"], p.get("teamPosition") or ""), []).append(p)
    parejas: list[tuple[str, Json, Json]] = []
    for pos in POSICIONES:
        azul, rojo = por_pos.get((100, pos), []), por_pos.get((200, pos), [])
        if len(azul) == 1 and len(rojo) == 1:
            parejas += [(pos, azul[0], rojo[0]), (pos, rojo[0], azul[0])]
    return parejas


def _eventos(frames: list[Json], jug: list[Json], legendarios: Collection[int]) -> _Eventos:
    nivel = {p["participantId"]: 1 for p in jug}
    eventos = _Eventos([], {}, {}, [])
    for f in frames:
        for e in f.get("events", []):
            ty = e["type"]
            if ty == "LEVEL_UP":
                nivel[e["participantId"]] = e["level"]
            elif ty == "CHAMPION_KILL":
                implicados = {e.get("killerId", 0), e["victimId"], *(e.get("assistingParticipantIds") or [])} - {0}
                eventos.kills.append(
                    (e["timestamp"], e.get("killerId", 0), e["victimId"], implicados, e.get("position") or {}, dict(nivel))
                )
            elif ty == "ITEM_PURCHASED" and e.get("itemId") in legendarios:
                eventos.compras.setdefault(e["participantId"], [e["itemId"], round(e["timestamp"] / MIN, 1)])
            elif ty == "SKILL_LEVEL_UP" and e.get("levelUpType", "NORMAL") == "NORMAL":
                eventos.habilidades.setdefault(e["participantId"], []).append(e["skillSlot"])
            elif ty == "ELITE_MONSTER_KILL":
                eventos.monstruos.append((e["timestamp"], e.get("monsterType", ""), e.get("killerTeamId", 0)))
    return eventos


def _marco(frames: list[Json], minuto: int, pid: int) -> Json | None:
    if minuto >= len(frames):
        return None
    marco: Json | None = frames[minuto]["participantFrames"].get(str(pid))
    return marco


def _cs(f: Json) -> int:
    cs: int = f.get("minionsKilled", 0) + f.get("jungleMinionsKilled", 0)
    return cs


def _registro(
    pos: str, a: Json, b: Json, info: Json, version: str, frames: list[Json], eventos: _Eventos, pid_equipo: dict[int, int]
) -> Registro:
    """El registro del duelo de a contra b, visto desde a."""
    A, B, eq = a["participantId"], b["participantId"], a["teamId"]
    f10 = _marco(frames, 10, A)
    peleas, muertes, m10, ka10 = _peleas_y_muertes(eventos.kills, A, B, eq, pid_equipo)
    r: Registro = {
        "pos": pos,
        "a": a["championId"],
        "b": b["championId"],
        "puuid": a.get("puuid", ""),
        "g": int(bool(a.get("win"))),
        "dur": round(info["gameDuration"] / 60, 1),
        "v": version,
        "dif": _diferencias(frames, A, B),
        "cs10": _cs(f10) if f10 else None,
        "peleas": peleas,
        "muertes": muertes,
        "m10": m10,
        "ka10": ka10,
        "item": eventos.compras.get(A),
        "runa": _runa(a),
        "hab": _orden_habilidades(eventos.habilidades.get(A, [])),
    }
    if pos == "JUNGLE":
        r.update(_de_jungla(frames, eventos.monstruos, A, B, eq))
    return r


def _diferencias(frames: list[Json], A: int, B: int) -> dict[str, list[int]]:
    """{minuto: [oro, experiencia, CS]} de a menos b a los 5, 10 y 15."""
    dif: dict[str, list[int]] = {}
    for minuto in (5, 10, 15):
        fa, fb = _marco(frames, minuto, A), _marco(frames, minuto, B)
        if fa and fb:
            dif[str(minuto)] = [fa["totalGold"] - fb["totalGold"], fa["xp"] - fb["xp"], _cs(fa) - _cs(fb)]
    return dif


def _peleas_y_muertes(
    kills: list[tuple[Any, ...]], A: int, B: int, eq: int, pid_equipo: dict[int, int]
) -> tuple[list[list[Any]], list[list[Any]], int, int]:
    """(peleas pequeñas entre los dos, muertes de a, muertes antes del 10, kills y asistencias antes del 10)."""
    peleas: list[list[Any]] = []
    muertes: list[list[Any]] = []
    m10 = ka10 = 0
    for ts, _killer, victima, implicados, posicion, niveles in kills:
        if ts < FIN_PELEAS and A in implicados and B in implicados and len(implicados) <= MAX_IMPLICADOS:
            gana = pid_equipo.get(victima) != eq
            peleas.append([round(ts / MIN, 1), niveles[A], niveles[B], int(gana), len(implicados), *_zona(posicion, eq)])
        if victima == A and ts < FIN_PELEAS:
            muertes.append([round(ts / MIN, 1), int(B in implicados), *_zona(posicion, eq)])
            m10 += ts < 10 * MIN
        elif A in implicados and victima != A and ts < 10 * MIN:
            ka10 += 1
    return peleas, muertes, m10, ka10


def _orden_habilidades(orden: list[int]) -> str:
    """'QWE>WQE': las tres primeras que sube y cuál maximiza antes (por cuántos puntos tiene al nivel 11)."""
    if not orden:
        return ""
    primeras = "".join("QWER"[s - 1] for s in orden[:3])
    maximiza = sorted("QWE", key=lambda s: (-orden[:11].count("QWER".index(s) + 1), "QWE".index(s)))
    return primeras + ">" + "".join(maximiza)


def _runa(p: Json) -> list[int] | None:
    """[runa clave, rama secundaria] o None."""
    estilos = (p.get("perks") or {}).get("styles") or []
    return [estilos[0]["selections"][0]["perk"], estilos[1]["style"]] if len(estilos) >= 2 else None


def _arriba(f: Json) -> bool:
    """¿Está por encima de la diagonal de mid (en la mitad de arriba del mapa)?"""
    arriba: bool = (f.get("position") or {}).get("y", 0) > (f.get("position") or {}).get("x", 0)
    return arriba


def _de_jungla(frames: list[Json], monstruos: list[tuple[int, str, int]], A: int, B: int, eq: int) -> Json:
    """Lo que solo se mira en jungla: larvas, primer dragón y si empezaron por el mismo lado."""
    propios = [m for m in monstruos if m[2] == eq]
    dragones = [m for m in monstruos if m[1] == "DRAGON"]
    extra: Json = {
        "larvas": sum(1 for m in propios if m[1] == "HORDE"),
        "drag1": int(dragones[0][2] == eq) if dragones else None,
    }
    fa, fb = _marco(frames, 2, A), _marco(frames, 2, B)
    if fa and fb:
        # Mismo lado del mapa (arriba o abajo de mid) a los 2:00: empezaron por el mismo lado.
        extra["mismo_lado"] = int(_arriba(fa) == _arriba(fb))
    return extra


# --- análisis de un duelo ---------------------------------------------------------------------------------
def _pct(v: float, n: int) -> int:
    return round(100 * v / n) if n else 0


def _media(xs: Iterable[float | None]) -> float | None:
    con_dato = [x for x in xs if x is not None]
    return statistics.fmean(con_dato) if con_dato else None


def _efecto(ganan: list[float | None], pierden: list[float | None]) -> float:
    """Diferencia entre medias en desviaciones típicas (d de Cohen): >0,3 ya se nota."""
    g, p = [x for x in ganan if x is not None], [x for x in pierden if x is not None]
    if len(g) < MIN_GRUPO or len(p) < MIN_GRUPO:
        return 0.0
    todo = g + p
    sd = statistics.pstdev(todo)
    return (statistics.fmean(g) - statistics.fmean(p)) / sd if sd else 0.0


def nombre_zona(z: list[Any]) -> str:
    tipo, lado, propia = z
    arriba = "de arriba" if lado == "sup" else "de abajo"
    if tipo == "jungla":
        return f"{'tu' if propia else 'su'} jungla {arriba}"
    if tipo == "rio":
        return f"el río {arriba}"
    if tipo == "base":
        return "tu base" if propia else "su base"
    nombre: str = {"top": "la línea de top", "mid": "mid", "bot": "la línea de bot"}.get(tipo, tipo)
    return nombre


def _num(x: float, dec: int = 1) -> str:
    return an.num(x, dec)


def analizar(
    registros: list[Registro],
    mios: list[Registro],
    nombre_a: str,
    nombre_b: str,
    pos: str,
    nombre_objeto: Callable[[int], str] = str,
    nombre_runa: Callable[[int], str] = str,
) -> Json:
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
    peleas = [p for r in registros for p in r["peleas"]]
    # (peso, texto, detalle), y "habito" al final en lo que hacen distinto los que ganan.
    datos: list[Dato] = [
        *_peleas_por_nivel(peleas, nombre_a, nombre_b),
        *_un_nivel_mas(peleas, nombre_a, nombre_b),
        *_por_delante_al_10(registros, nombre_a, nombre_b),
        *_si_escala(registros, nombre_a),
        *_habitos(ganan, pierden, nombre_a, nombre_b, pos),
        *_donde_muere(registros, nombre_a, nombre_b, pos),
    ]
    return {
        "n": n,
        "wr": _pct(len(ganan), n),
        "datos": [{"texto": d[1], "detalle": d[2]} for d in _elegidos(datos)],
        "build": _build(registros, nombre_objeto, nombre_runa),
        "poco": False,
    }


def _elegidos(datos: list[Dato]) -> list[Dato]:
    """Los cuatro datos que más pesan. Lo que hacen distinto los que ganan es lo más aprovechable: al menos uno
    entra siempre."""
    datos.sort(key=lambda d: d[0], reverse=True)
    elegidos = datos[:4]
    habito = next((d for d in datos if len(d) > 3), None)
    if habito and habito not in elegidos:
        elegidos[-1] = habito
    return elegidos


def _ganadas(lista: list[Any], i: int | str) -> int:
    """Porcentaje de las peleas (i=3) o partidas ("g") de la lista que acaban bien para a."""
    return _pct(sum(x[i] for x in lista), len(lista))


def _peleas_por_nivel(peleas: list[list[Any]], nombre_a: str, nombre_b: str) -> list[Dato]:
    """1. Peleas entre los dos antes y después del 6 (o todas juntas, si no hay bastantes de cada)."""
    antes = [p for p in peleas if p[1] < 6]
    despues = [p for p in peleas if p[1] >= 6]
    if len(antes) >= MIN_PELEAS and len(despues) >= MIN_PELEAS:
        pa, pd = _ganadas(antes, 3), _ganadas(despues, 3)
        return [
            (
                abs(pa - pd) + abs(pa - 50) / 2,
                f"{nombre_a} gana el {pa}% de las peleas con {nombre_b} antes de su 6; desde el 6, el {pd}%.",
                f"{len(antes)} y {len(despues)} peleas de 2 a 4 jugadores antes del 15",
            )
        ]
    if len(peleas) >= MIN_PELEAS:
        pt = _ganadas(peleas, 3)
        return [
            (
                abs(pt - 50),
                f"{nombre_a} gana el {pt}% de las peleas con {nombre_b} antes del 15.",
                f"{len(peleas)} peleas de 2 a 4 jugadores",
            )
        ]
    return []


def _un_nivel_mas(peleas: list[list[Any]], nombre_a: str, nombre_b: str) -> list[Dato]:
    """Cuánto cambian las peleas con un nivel de ventaja."""
    ventaja = [p for p in peleas if p[1] > p[2]]
    igual = [p for p in peleas if p[1] == p[2]]
    if len(ventaja) < MIN_PELEAS or len(igual) < MIN_PELEAS:
        return []
    pv, pi = _ganadas(ventaja, 3), _ganadas(igual, 3)
    if pv - pi < 10:
        return []
    return [
        (
            pv - pi,
            f"Con un nivel más que {nombre_b}, {nombre_a} gana el {pv}% de las peleas; a la par, el {pi}%.",
            f"{len(ventaja)} y {len(igual)} peleas",
        )
    ]


def _por_delante_al_10(registros: list[Registro], nombre_a: str, nombre_b: str) -> list[Dato]:
    """2. Cuánto pesa ir por delante al 10."""
    con10 = [r for r in registros if "10" in r["dif"]]
    delante = [r for r in con10 if r["dif"]["10"][0] >= 500]
    detras = [r for r in con10 if r["dif"]["10"][0] <= -500]
    if len(delante) < MIN_GRUPO or len(detras) < MIN_GRUPO:
        return []
    wd, wt = _ganadas(delante, "g"), _ganadas(detras, "g")
    return [
        (
            abs(wd - wt) / 2,
            f"{nombre_a} con +500 de oro sobre {nombre_b} al 10 gana el {wd}% de las partidas; con −500, el {wt}%.",
            f"{len(delante)} y {len(detras)} partidas",
        )
    ]


def _si_escala(registros: list[Registro], nombre_a: str) -> list[Dato]:
    """3. Si escala o se decide pronto."""
    cortas = [r for r in registros if r["dur"] < 25]
    largas = [r for r in registros if r["dur"] >= 32]
    if len(cortas) < MIN_GRUPO or len(largas) < MIN_GRUPO:
        return []
    wc, wl = _ganadas(cortas, "g"), _ganadas(largas, "g")
    if abs(wc - wl) < 10:
        return []
    return [
        (
            abs(wc - wl),
            f"{nombre_a} gana el {wc}% de las partidas que acaban antes del 25 y el {wl}% de las que pasan del 32.",
            f"{len(cortas)} y {len(largas)} partidas",
        )
    ]


# Lo que se mide de cada registro (None si ese registro no lo tiene), para los hábitos y para compararte.
def _muertes_10(r: Registro) -> int:
    muertes: int = r["m10"]
    return muertes


def _peleas_antes_del_6(r: Registro) -> int:
    return sum(1 for p in r["peleas"] if p[1] < 6)


def _cs_10(r: Registro) -> int | None:
    cs: int | None = r["cs10"]
    return cs


def _cs_sobre_el_rival_10(r: Registro) -> int | None:
    cs: int | None = (r["dif"].get("10") or [None] * 3)[2]
    return cs


def _oro_sobre_el_rival_10(r: Registro) -> int | None:
    oro: int | None = (r["dif"].get("10") or [None])[0]
    return oro


def _habitos_de(pos: str, nombre_b: str) -> list[tuple[str, Medida, int | None]]:
    """Lo que se mira de cada registro: (qué es, cómo se saca, decimales; None si es un porcentaje)."""
    habitos: list[tuple[str, Medida, int | None]] = [
        ("muertes antes del 10", _muertes_10, 1),
        (f"peleas con {nombre_b} antes del 6", _peleas_antes_del_6, 1),
        ("kills y asistencias antes del 10", lambda r: r["ka10"], 1),
    ]
    if pos == "JUNGLE":
        habitos.append(("CS al 10", _cs_10, 0))
    elif pos != "UTILITY":
        habitos.append((f"diferencia de CS con {nombre_b} al 10", _cs_sobre_el_rival_10, 1))
    if pos == "JUNGLE":
        habitos += [("larvas", lambda r: r.get("larvas"), 1), ("primer dragón", lambda r: r.get("drag1"), None)]
    return habitos


def _habitos(ganan: list[Registro], pierden: list[Registro], nombre_a: str, nombre_b: str, pos: str) -> list[Dato]:
    """4. Qué hacen distinto los que ganan este duelo: los dos hábitos que más se notan."""
    candidatos: list[tuple[float, str, Medida, int | None]] = []
    for nombre, fn, dec in _habitos_de(pos, nombre_b):
        d = _efecto([fn(r) for r in ganan], [fn(r) for r in pierden])
        if abs(d) >= 0.3:
            candidatos.append((abs(d), nombre, fn, dec))
    datos: list[Dato] = []
    for d, nombre, fn, dec in sorted(candidatos, reverse=True)[:2]:
        mg, mp = _media(fn(r) for r in ganan), _media(fn(r) for r in pierden)
        if mg is None or mp is None:  # no pasa: _efecto ya ha visto bastantes datos en los dos grupos
            continue
        if dec is None:
            texto = (
                f"Primer dragón para tu equipo: {round(100 * mg)}% en las que gana {nombre_a}, "
                f"{round(100 * mp)}% en las que pierde."
            )
        else:
            texto = (
                f"{nombre[0].upper() + nombre[1:]}: {_num(mg, dec)} en las que gana {nombre_a}, "
                f"{_num(mp, dec)} en las que pierde."
            )
        datos.append((25 * d, texto, f"{len(ganan)} victorias y {len(pierden)} derrotas", "habito"))
    return datos


def _donde_muere(registros: list[Registro], nombre_a: str, nombre_b: str, pos: str) -> list[Dato]:
    """5. Dónde muere a con b de por medio."""
    muertes = [m for r in registros for m in r["muertes"] if m[1]]
    if len(muertes) < MIN_PELEAS:
        return []
    zonas = Counter(nombre_zona(m[2:]) for m in muertes)
    zona, veces = zonas.most_common(1)[0]
    # Que un jugador de línea muera en su línea no dice nada.
    propia = {"TOP": "la línea de top", "MIDDLE": "mid", "BOTTOM": "la línea de bot", "UTILITY": "la línea de bot"}.get(pos)
    if veces / len(muertes) < 0.25 or zona == propia:
        return []
    return [
        (
            100 * veces / len(muertes) - 15,
            f"El {_pct(veces, len(muertes))}% de las muertes de {nombre_a} con {nombre_b} de por medio "
            f"antes del 15 son en {zona}.",
            f"{len(muertes)} muertes",
        )
    ]


def _build(registros: list[Registro], nombre_objeto: Callable[[int], str], nombre_runa: Callable[[int], str]) -> Json | None:
    """Lo más jugado en este duelo y cómo le va. Va aparte y en pequeño."""
    runas = Counter(tuple(r["runa"]) for r in registros if r.get("runa"))
    objetos = Counter(r["item"][0] for r in registros if r.get("item"))
    habs = Counter(r["hab"].split(">")[1] for r in registros if r.get("hab"))
    if not (runas and objetos):
        return None
    runa = runas.most_common(1)[0][0]
    obj = objetos.most_common(1)[0][0]
    con_obj = [r for r in registros if r.get("item") and r["item"][0] == obj]
    return {
        "runa": nombre_runa(runa[0]),
        "secundaria": nombre_runa(runa[1]),
        "objeto": nombre_objeto(obj),
        "minuto": _num(statistics.median(r["item"][1] for r in con_obj)),
        "wr_objeto": _ganadas(con_obj, "g"),
        "n_objeto": len(con_obj),
        "maximiza": " > ".join(habs.most_common(1)[0][0]) if habs else "",
    }


def metricas(pos: str) -> list[tuple[str, Medida, int, bool]]:
    """Lo que se compara entre tú y tu referencia: (nombre, función del registro, decimales, con signo)."""
    filas: list[tuple[str, Medida, int, bool]] = [
        ("Muertes antes del 10", _muertes_10, 1, False),
        ("Peleas con tu rival antes del 6", _peleas_antes_del_6, 1, False),
    ]
    if pos == "JUNGLE":
        filas.append(("CS al 10", _cs_10, 0, False))
    elif pos != "UTILITY":
        filas.append(("CS sobre tu rival al 10", _cs_sobre_el_rival_10, 0, True))
    filas.append(("Oro sobre tu rival al 10", _oro_sobre_el_rival_10, 0, True))
    return filas


def comparar(mios: list[Registro], referencia: list[Registro], pos: str, nombre_ref: str, minimo: int = MIN_GRUPO) -> Json | None:
    """Tus medias al lado de las de tu referencia (los que ganan el duelo, Challenger, un jugador...).

    Con una sola partida tuya sirve para la revisión: tu partida contra lo que hace tu referencia.
    """
    if not mios or len(referencia) < minimo:
        return None
    filas: list[Json] = []
    for nombre, fn, dec, con_signo in metricas(pos):
        t, g = _media(fn(r) for r in mios), _media(fn(r) for r in referencia)
        if t is not None and g is not None:
            tu, ref = _formato(t, dec, con_signo), _formato(g, dec, con_signo)
            filas.append({"que": nombre, "tu": tu, "ref": ref, "mejor": _mejor(nombre, t, g)})
    return {"n": len(mios), "n_ref": len(referencia), "ref": nombre_ref, "filas": filas}


def _formato(x: float, dec: int, con_signo: bool) -> str:
    """Una media para la tabla: con signo y sin decimales (lo que va sobre el rival), o con sus decimales."""
    return f"{x:+.0f}" if con_signo else _num(x, dec)


def _mejor(nombre: str, tu: float, ref: float) -> bool | None:
    """Si tu número es mejor (True), peor (False) o parecido (None) que el de tu referencia."""
    if nombre.startswith("Muertes"):
        dif = ref - tu
    elif nombre.startswith("Peleas"):
        return None  # pelear más o menos no es mejor ni peor por sí mismo
    else:
        dif = tu - ref
    margen = 0.25 if nombre.startswith("Muertes") else (5 if "CS" in nombre else 150)
    return None if abs(dif) < margen else dif > 0
