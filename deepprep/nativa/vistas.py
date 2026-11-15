"""Lo que pinta cada vista de la interfaz, ya decidido: qué texto sale, con qué tono y en qué orden.

El QML solo coloca. Esto es Python puro, sin Qt, y se prueba con unittest (tests/test_nativa.py). Hasta la 2.0 lo hacía
el panel web en JavaScript; al pasar a Qt se tradujo función a función, con los mismos textos y umbrales.

Los textos con trozos de distinto estilo (una cifra en mono, un nombre en negrita, un % en verde) van como RichText de
Qt, hecho aquí: todo lo que viene de la app pasa por esc(), así que un nombre con «<» no puede meter etiquetas.
"""

import html
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from .. import config
from ..analisis import NOMBRE_POS
from ..constantes import MODOS, modo_activo
from . import oro

Json = dict[str, Any]

# Los colores de Tema.qml (los de web/estilo.css), para los trozos de RichText. Una prueba mira que coincidan.
COLOR = {
    "texto": "#f4f5f6",
    "texto2": "#a3aab4",
    "texto3": "#79808b",
    "acento": "#8b7cf6",
    "aliado": "#4790ec",
    "rival": "#e5534d",
    "bien": "#40cf8f",
    "mal": "#f2706a",
}
TONO = {"bien": "bien", "mal": "mal", "suave": "texto3", "ojo": "texto", "aliado": "aliado", "rival": "rival"}
MONO = "IBM Plex Mono"

ROLES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "UTILITY": "utility"}
ROL_TXT = {"TOP": "Top", "JUNGLE": "Jungla", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}
OPCIONES_ROL = [{"id": r, "txt": t} for r, t in ROL_TXT.items()]
# Lo que abarca cada modo en Ajustes, cuando el nombre no lo dice todo.
NOTA_MODO = {
    "normales": "Reclutamiento, a ciegas, partida rápida y Swiftplay.",
    "aram": "También ARAM: Caos y el Clash de ARAM. Lo básico: rango y maestría.",
    "arena": "Lo básico: rango y maestría.",
    "otros": "URF, Uno para todos, contra la IA, personalizadas… Lo básico.",
}
TITULOS = {"partida": "Partida", "revisiones": "Revisiones", "ajustes": "Ajustes"}
NIVEL_TXT = {
    "iron": "Hierro",
    "bronze": "Bronce",
    "silver": "Plata",
    "gold": "Oro",
    "platinum": "Platino",
    "emerald": "Esmeralda",
    "diamond": "Diamante",
    "master": "Maestro",
    "grandmaster": "Gran Maestro",
    "challenger": "Aspirante",
}
SIN_DIVISION = ("master", "grandmaster", "challenger")
DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic")
HORA_CORTE = 6  # una sesión de madrugada cuenta para el día anterior: «hoy» empieza a las 6:00


# --- trozos de RichText -----------------------------------------------------------------------------------
def esc(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _color(tono: str) -> str:
    return f"color:{COLOR[TONO[tono]]};" if tono in TONO else ""


def num(txt: object, tono: str = "") -> str:
    """Una cifra: en mono y, si toca, con el color de su tono."""
    return f"<span style=\"font-family:'{MONO}';{_color(tono)}\">{esc(txt)}</span>"


def b(txt: object, tono: str = "") -> str:
    """En negrita y en el color del texto principal."""
    return f'<span style="font-weight:600;{_color(tono) or "color:" + COLOR["texto"] + ";"}">{esc(txt)}</span>'


def con_tono(txt: object, tono: str) -> str:
    return f'<span style="{_color(tono)}">{esc(txt)}</span>' if tono in TONO else esc(txt)


# --- cifras y textos ----------------------------------------------------------------------------------------
def pct(v: float, n: float) -> int:
    """Porcentaje redondeado con el .5 hacia arriba (como Math.round, no como round de Python)."""
    return math.floor(100 * v / n + 0.5) if n else 0


def clase_wr(v: float, n: float) -> str:
    """Verde o rojo solo con muestra suficiente; el color describe al jugador, no a ti."""
    if n < 5:
        return ""
    p = pct(v, n)
    return "bien" if p >= 58 else "mal" if p <= 42 else ""


def miles(n: float) -> str:
    return f"{math.floor(n / 1000 + 0.5)}k" if n >= 1000 else str(n)


def coma(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def numero(s: object) -> float:
    """Cifra ya formateada por la app -> número, para dibujar barras: '−150' -> -150, '6,8' -> 6.8, '64%' -> 64."""
    limpio = re.sub(r"[^\d,.\-−+]", "", str(s)).replace("−", "-").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return math.nan


def lp(cambio: int | None) -> Json:
    """+21 → {'txt': '+21 LP', 'tono': 'bien'}. Con el menos tipográfico."""
    if cambio is None:
        return {"txt": "", "tono": "suave"}
    signo, tono = ("+", "bien") if cambio > 0 else ("−", "mal") if cambio < 0 else ("±", "suave")
    return {"txt": f"{signo}{abs(cambio)} LP", "tono": tono}


def diferencia(a: float, b_: float, sufijo: str = "") -> Json:
    d = a - b_
    signo = "+" if d > 0 else "−" if d < 0 else ""
    return {"txt": f"{signo}{abs(d)}{sufijo}", "tono": "bien" if d > 0 else "mal" if d < 0 else "suave"}


def teclas(atajo: str | None) -> list[str]:
    """'ctrl+tab' -> ['CTRL', 'TAB']."""
    return [k.strip().upper() for k in atajo.split("+")] if atajo else []


def fecha(ms: float) -> str:
    """Como la escribe Windows en español: 'sáb, 7 nov, 23:10'."""
    d = datetime.fromtimestamp(ms / 1000)
    return f"{DIAS[d.weekday()]}, {d.day} {MESES[d.month - 1]}, {d:%H:%M}"


def liga(l: Mapping[str, Any]) -> str:
    nivel = NIVEL_TXT.get(l.get("nivel", ""), l.get("nivel", ""))
    division = "" if l.get("nivel") in SIN_DIVISION else f" {l.get('rank', '')}"
    return f"{nivel}{division} · {l.get('lp', 0)} LP"


def imagen(url: str | None) -> str:
    """Las imágenes para Qt: las de Data Dragon por image://ddragon (ddragon.imagen, con su caché en disco) y las propias
    (/img/rango/...) de deepprep/recursos. Vacío si no hay."""
    if not url:
        return ""
    if url.startswith("/ddragon/"):
        return "image://ddragon/" + url.removeprefix("/ddragon/").rsplit(".", 1)[0]
    if url.startswith("/img/"):
        return (config.RUTA_RECURSOS / url.removeprefix("/")).as_uri()
    return ""


def icono_rango(nivel: str) -> str:
    return imagen(f"/img/rango/{nivel}.svg") if re.fullmatch(r"[a-z]+", nivel or "") else ""


def etapa(modo: str | None, p: Mapping[str, Any]) -> str:
    if p.get("terminada"):
        return "Partida terminada"
    return "En partida" if modo == "juego" else "Pantalla de carga" if modo == "carga" else "En vivo"


def racha(lista: Sequence[bool] | None) -> Json | None:
    """La más reciente a la derecha, como se lee una racha (la app las da de la más reciente a la más vieja)."""
    if not lista:
        return None
    v = sum(1 for g in lista if g)
    return {
        "items": [bool(g) for g in reversed(lista)],
        "titulo": f"Últimas {len(lista)}: {v}V {len(lista) - v}D, la más reciente a la derecha",
    }


def barra_wr(v: float, n: float) -> Json:
    """Barra de % de victorias con la marca del 50 %. El color lo lleva la cifra, no la barra."""
    return {"ancho": pct(v, n) / 100, "titulo": f"{v} de {n}"}


def rol(r: str | None) -> Json:
    return {"icono": ROLES.get(r or "", ""), "txt": ROL_TXT.get(r or "", r or "")}


def elegir_rol(r: Mapping[str, Any] | None) -> Json | None:
    """El selector de tu posición en esta partida y por qué es esa; None si no se puede cambiar (la partida de otro o
    fuera de la Grieta)."""
    if not r or not r.get("elegible"):
        return None
    return {"opciones": OPCIONES_ROL, "actual": r.get("actual", ""), "motivo": r.get("motivo", "")}


def rango(f: Mapping[str, Any], compacto: bool = False) -> Json:
    """El rango de solo/dúo de una fila: oculto, cargando, sin rango o con rango (y el de flex si cabe)."""
    if f.get("oculto"):
        return {"estado": "oculto", "linea2": "Perfil oculto"}
    l = f.get("liga")
    if not l:
        return {"estado": "cargando"}
    s = l.get("solo")
    flex = f" · Flex {l['flex']['txt']}" if l.get("flex") and not compacto else ""
    if not s:
        return {"estado": "sin", "icono": icono_rango("unranked"), "txt": "Sin rango", "linea2": esc("en solo/dúo" + flex)}
    total = s["v"] + s["d"]
    detalle = esc(f"{s['lp']} LP")
    if not compacto and total:
        detalle += " · " + con_tono(f"{pct(s['v'], total)}%", clase_wr(s["v"], total))
    return {
        "estado": "ok",
        "icono": icono_rango(s["nivel"]),
        "txt": s["txt"],
        "linea2": f"<span style=\"font-family:'{MONO}'\">{detalle}</span>{esc(flex)}",
        "titulo": f"{s['v']}V {s['d']}D en solo/dúo" if total else "",
    }


def etiquetas(lista: Sequence[Mapping[str, Any]], maximo: int = 0) -> list[Json]:
    l = list(lista)[:maximo] if maximo else list(lista)
    return [{"t": e.get("t", ""), "tono": e.get("tono", ""), "d": e.get("d", "")} for e in l]


def grafico_gank(valor: object) -> Json | None:
    """'min 4:33 · top 4 · mid 1 · bot 2' -> una barra por línea; si el texto no tiene ese formato, nada."""
    lineas = [(m.group(1), int(m.group(2))) for m in re.finditer(r"\b(top|mid|bot)\s+(\d+)", str(valor))]
    if len(lineas) < 2:
        return None
    maximo = max(n for _, n in lineas) or 1
    total = sum(n for _, n in lineas)
    return {
        "filas": [{"l": l, "n": n, "ancho": n / maximo, "tip": f"{l} · {n} de {total}"} for l, n in lineas],
        "aria": "Primer gank por línea: " + ", ".join(f"{l} {n}" for l, n in lineas),
    }


def tarjetas(j: Mapping[str, Any], compacto: bool = False) -> list[Json]:
    """Las tarjetas del jungla rival; la del primer gank, con su gráfico (salvo en el overlay)."""

    def gank(t: Mapping[str, Any]) -> Json | None:
        return None if compacto or not re.search("gank", t.get("titulo", ""), re.I) else grafico_gank(t.get("valor", ""))

    return [
        {
            "titulo": t.get("titulo", ""),
            "valor": t.get("valor", ""),
            "tono": t.get("tono", ""),
            "detalle": "" if compacto else t.get("detalle", ""),
            "gank": gank(t),
        }
        for t in j.get("tarjetas") or []
    ]


def filas_vs(vs: Sequence[Mapping[str, Any]], mi_campeon: str) -> Json:
    """Tu historial contra los campeones de la partida (panel y selección de campeón)."""
    filas = []
    for f in vs:
        if not f.get("n"):
            continue
        mio = f"con {esc(mi_campeon)} " + b(f"{f['v_mio']}V {f['n_mio'] - f['v_mio']}D") if f.get("n_mio") else ""
        total = con_tono("total", "suave") + " " + num(f"{f['v']}V {f['n'] - f['v']}D", clase_wr(f["v"], f["n"]))
        filas.append({"retrato": imagen(f.get("icono")), "nombre": f.get("nombre", ""), "mio": mio, "total": total})
    sin = [f.get("nombre", "") for f in vs if not f.get("n")]
    return {"filas": filas, "sin": f"Sin cruces con {', '.join(sin)}." if sin else ""}


def notas(lista: Sequence[Mapping[str, Any]] | None) -> list[Json]:
    """Tus notas por campeón (las escribes en Ajustes)."""
    return [
        {
            "retrato": imagen(n.get("icono")),
            "campeon": n.get("campeon", ""),
            "rival": bool(n.get("rival")),
            "texto": n.get("texto", ""),
        }
        for n in lista or []
    ]


# --- duelo -------------------------------------------------------------------------------------------------
def tabla_comparacion(c: Mapping[str, Any] | None, pie: str) -> Json | None:
    """Tú (violeta) contra tu referencia (gris): barras emparejadas, cada fila con su escala. Si hay negativos, desde
    el centro. pie: texto ya escapado."""
    if not c or not c.get("filas"):
        return None
    filas = []
    for f in c["filas"]:
        a, r = numero(f.get("tu")), numero(f.get("ref"))
        barras = None
        if math.isfinite(a) and math.isfinite(r) and (a or r):
            maximo = max(abs(a), abs(r))
            centro = a < 0 or r < 0

            def barra(v: float, centro: bool = centro, maximo: float = maximo) -> Json:
                w = 0.5 * abs(v) / maximo
                if centro:
                    return {"x": 0.5 - w if v < 0 else 0.5, "ancho": w}
                return {"x": 0.0, "ancho": 2 * w}

            barras = {"centro": centro, "tu": barra(a), "ref": barra(r)}
        mejor = f.get("mejor")
        filas.append(
            {
                "que": f.get("que", ""),
                "tu": f.get("tu", ""),
                "tu_tono": "bien" if mejor is True else "mal" if mejor is False else "",
                "ref": f.get("ref", ""),
                "barras": barras,
            }
        )
    return {
        "ref": c.get("ref", ""),
        "filas": filas,
        "pie": f"{pie} {esc(c.get('ref', ''))}: media de {c.get('n_ref', 0)} partidas. Se cambia en Ajustes.",
    }


def duelo(d: Mapping[str, Any] | None, compacto: bool = False) -> Json | None:
    """Tu duelo contra el rival directo (Master+). Solo antes de empezar; compacto: el del overlay (dos datos, sin
    tablas ni build)."""
    if not d:
        return None
    a, pos = esc(d.get("a", "")), esc(d.get("pos", ""))
    n_tu = (d.get("tu") or {}).get("n", 0)
    out: Json = {
        "titulo": f"Tu duelo · {d.get('pos', '')}",
        "sub": f"{d.get('n', 0)} partidas de Master+",
        "a": d.get("a", ""),
        "b": d.get("b", ""),
        "icono_a": imagen(d.get("icono_a")),
        "icono_b": imagen(d.get("icono_b")),
        "poco": bool(d.get("poco")),
        "wr": None if d.get("poco") else {"txt": f"{d.get('wr', 0)}%", "linea2": f"gana {d.get('a', '')}"},
        "motivo": "",
        "datos": [],
        "tu": None,
        "build": "",
    }
    if d.get("poco"):
        out["motivo"] = (
            "Aún hay pocas partidas de este duelo; el recolector sigue buscando."
            if d.get("en_pool")
            else f"{d.get('a', '')} en {d.get('pos', '')} no está entre tus campeones más jugados, "
            "así que no se recogen sus partidas."
        )
        if not compacto:
            out["tu"] = tabla_comparacion(d.get("tu"), f"Tú: tus {n_tu} partidas con {a} de {pos}.")
        return out
    datos = list(d.get("datos") or [])
    out["datos"] = [
        {"texto": x.get("texto", ""), "detalle": "" if compacto else x.get("detalle", "")}
        for x in (datos[:2] if compacto else datos)
    ]
    if not compacto:
        out["tu"] = tabla_comparacion(d.get("tu"), f"Tú: tus {n_tu} partidas con {a} de {pos}, contra cualquiera.")
        bu = d.get("build")
        if bu:
            maximiza = f" · {esc(bu['maximiza'])}" if bu.get("maximiza") else ""
            out["build"] = (
                f"{esc(bu.get('runa', ''))} + {esc(bu.get('secundaria', ''))} · {esc(bu.get('objeto', ''))} "
                + con_tono(f"(min {bu.get('minuto', '')}, gana {bu.get('wr_objeto', 0)}% de {bu.get('n_objeto', 0)})", "suave")
                + maximiza
            )
    return out


# --- pestaña Partida: el panel ----------------------------------------------------------------------------
def fila(f: Mapping[str, Any], basico: bool = False) -> Json:
    """Un jugador de la tabla de equipos. basico: fuera de la Grieta, sin sus últimas partidas (no se piden)."""
    muestra = f.get("muestra") or {}
    forma: Json | None = None
    con_campeon: Json | None = None
    if muestra.get("n") and not basico:
        n, v = muestra["n"], muestra["v"]
        forma = {"txt": num(f"{v}V", clase_wr(v, n)) + " " + num(f"{n - v}D", "suave"), "racha": racha(f.get("racha"))}
        c = f.get("camp") or {}
        if c.get("n"):
            con_campeon = {
                "txt": num(f"{pct(c['v'], c['n'])}%", clase_wr(c["v"], c["n"])) + " " + num(f"{c['v']}/{c['n']}", "suave"),
                "barra": barra_wr(c["v"], c["n"]),
                "kda": " / ".join(coma(x) for x in c["kda"]) if c.get("kda") else "",
            }
        else:
            con_campeon = {"ninguna": True}
    maestria = "" if f.get("maestria") is None else f" · {miles(f['maestria'])}"
    mains = f.get("mains") or []
    nombre, tag = f.get("nombre") or "", f.get("tag") or ""
    return {
        "soy_yo": bool(f.get("soy_yo")),
        # Al pulsar el nombre se copia, para buscarlo luego en op.gg o donde sea. Un perfil oculto no tiene.
        "riot_id": f"{nombre}#{tag}" if nombre and tag and not f.get("oculto") else "",
        "rol": rol(f.get("rol")),
        "retrato": imagen(f.get("icono")),
        "nombre": f.get("nombre", ""),
        "tag": f.get("tag") or "",
        "campeon": f"{f.get('campeon', '')}{maestria}",
        "mains": "Más jugados: " + ", ".join(f"{m['nombre']} {miles(m['puntos'])}" for m in mains) if mains else "",
        "etiquetas": etiquetas(f.get("etiquetas") or []),
        "rango": rango(f),
        "forma": forma,
        "cargando": "" if f.get("oculto") or basico else "cargando…",
        "con_campeon": con_campeon,
    }


def en_mapa(x: float, y: float) -> list[float]:
    """Del mapa del juego a la imagen del minimapa de Data Dragon (de 0 a 1): cubre de (-120, -120) a (14870, 14980) y
    el eje y de la imagen va hacia abajo."""
    return [round((x + 120) / 14990, 4), round(1 - (y + 120) / 15100, 4)]


def mapa_jungla(j: Mapping[str, Any]) -> Json | None:
    """Dónde estaba el jungla rival en sus partidas a cada minuto, ya girado al lado del mapa que le toca hoy."""
    mapa = j.get("mapa") or {}
    if not mapa:
        return None
    minutos = sorted(mapa, key=lambda m: int(m))
    return {
        "minutos": minutos,
        "inicial": "3" if "3" in minutos else minutos[0],
        "puntos": {m: [en_mapa(x, y) for x, y in mapa[m]] for m in minutos},
        "campeon": j.get("campeon", ""),
    }


def jungla(j: Mapping[str, Any] | None) -> Json:
    if not j:
        return {"vacio": "No identifico al jungla rival."}
    campeon = esc(j.get("campeon", ""))
    if j.get("n"):
        nota = f"{j['n']} partidas de jungla · {j.get('n_campeon', 0)} con {campeon} · {j.get('n_lineas', 0)} líneas de tiempo"
        nota += " · cargando más" if j.get("cargando") else ""
    else:
        nota = "cargando sus partidas…" if j.get("cargando") else "sin partidas de jungla recientes"
    return {
        "campeon": j.get("campeon", ""),
        "nombre": j.get("nombre", ""),
        "retrato": imagen(j.get("icono")),
        "nota": f"{esc(j.get('nombre', ''))} · {nota}",
        "mapa": mapa_jungla(j),
        "tarjetas": tarjetas(j),
    }


def rival_linea(r: Mapping[str, Any] | None) -> Json | None:
    """Tu rival de línea cuando no juegas jungla: como la caja del jungla rival, sin su mapa. None si juegas jungla."""
    if not r:
        return None
    campeon = esc(r.get("campeon", ""))
    pos = NOMBRE_POS.get(r.get("rol", ""), "")  # en minúscula: va en mitad de la frase
    if r.get("n"):
        nota = f"{r['n']} partidas de {pos} · {r.get('n_campeon', 0)} con {campeon} · {r.get('n_lineas', 0)} líneas de tiempo"
        nota += " · cargando más" if r.get("cargando") else ""
    else:
        nota = "cargando sus partidas…" if r.get("cargando") else f"sin partidas de {pos} recientes"
    return {
        "titulo": "Tu rival de línea",
        "sub": f"de sus partidas recientes de {pos}",
        "campeon": r.get("campeon", ""),
        "nombre": r.get("nombre", ""),
        "retrato": imagen(r.get("icono")),
        "nota": f"{esc(r.get('nombre', ''))} · {nota}",
        "mapa": None,
        "tarjetas": tarjetas(r),
    }


def lineas(ls: Sequence[Mapping[str, Any]], gank: Mapping[str, Any] | None, modo: str | None) -> Json:
    return {
        "titulo": "Líneas" if modo == "juego" else "Dónde va a haber errores",
        "lineas": [
            {
                "linea": l.get("linea", ""),
                "veredicto": l.get("veredicto") or "",
                "tono": l.get("tono", ""),
                "motivos": [{"t": m, "aliado": False} for m in l.get("rival") or []]
                + [{"t": m, "aliado": True} for m in l.get("aliado") or []],
            }
            for l in ls
        ],
        "pie": f"Su primer gank fue a {b(gank['linea'])} en {gank['veces']} de {gank['n']} partidas." if gank else "",
    }


def historial(h: Mapping[str, Any] | None) -> Json | None:
    if not h:
        return None
    alcance = (
        f"tus {h.get('n', 0)} clasificatorias{h.get('cola_txt', '')} de la temporada"
        if h.get("alcance") == "temporada"
        else f"muestra de {h.get('n', 0)} partidas"
    )
    if not h.get("n"):
        return {"sub": alcance, "vacio": "Aún no hay partidas tuyas guardadas; se están descargando."}
    c = h.get("campeon") or {}
    mi = h.get("mi_campeon", "")
    conocidos = []
    for k in h.get("conocidos") or []:
        cuando = f"hace {k['dias']} d" if k.get("dias") else "hoy"
        veces = f", {k['veces']} veces" if k.get("veces", 0) > 1 else ""
        conocidos.append(
            f"Ya jugaste {'con' if k.get('contigo') else 'contra'} {b(k.get('nombre', ''))} {cuando} "
            f"({'ganaste' if k.get('ganaste') else 'perdiste'}){veces}."
        )
    return {
        "sub": alcance,
        "vacio": "",
        "cifra": (
            {
                "txt": f"{pct(c['v'], c['n'])}%",
                "tono": clase_wr(c["v"], c["n"]),
                "linea2": f"con {esc(mi)} · " + num(f"{c['v']}V {c['n'] - c['v']}D"),
            }
            if c.get("n")
            else None
        ),
        "sin": "" if c.get("n") else f"Sin partidas con {mi}.",
        "racha": racha(c.get("racha")) if c.get("n") else None,
        "vs": filas_vs(h.get("vs") or [], mi),
        "conocidos": conocidos,
    }


def estado_carga(p: Mapping[str, Any], cuota: Mapping[str, Any]) -> Json:
    prog = p.get("progreso") or {"hechas": 0, "total": 0}
    cargando = prog["hechas"] < prog["total"]
    txt = f"Cargando {prog['hechas']} de {prog['total']} consultas" if cargando else "Datos completos"
    if cargando and (cuota.get("espera") or 0) > 1:
        txt += f" · Riot deja seguir en {math.ceil(cuota['espera'])} s"
    return {"cargando": cargando, "txt": txt, "ancho": pct(prog["hechas"], prog["total"]) if prog["total"] else 0}


def panel(e: Mapping[str, Any]) -> Json:
    """La pestaña Partida con una partida (pantalla de carga, en juego o ya terminada)."""
    p = e["panel"]
    modo = e.get("modo")
    c = estado_carga(p, e.get("cuota") or {})
    yo = p.get("yo") or {}
    mi_fila = next((f for f in p["equipos"]["aliado"] if f.get("soy_yo")), None)
    # Fuera de la Grieta (ARAM, Arena...), lo básico de cada jugador: ni jungla, ni líneas, ni duelo, ni plan.
    basico = not p.get("completo", True)
    sub = f"En {p.get('cola', '')} no hay posiciones: de cada jugador, su rango y su maestría con el campeón. " if basico else ""
    return {
        "basico": basico,
        "hero": {
            "retrato": imagen(mi_fila.get("icono")) if mi_fila else "",
            "cabecera": f"{p.get('cola', '')} · {etapa(modo, p)}",
            "titulo": yo.get("campeon") or "Partida en vivo",
            "rol": ROL_TXT.get(mi_fila.get("rol", ""), "") if mi_fila else "",
            "sub": esc(sub) + c["txt"],
            "bans": [{"retrato": imagen(x.get("icono")), "nombre": x.get("nombre", "")} for x in p.get("bans") or []],
            "carga": c,
        },
        # Ya acabada no hay nada que cambiar.
        "elegir_rol": None if p.get("terminada") else elegir_rol(p.get("rol")),
        "aliado": [fila(f, basico) for f in p["equipos"]["aliado"]],
        "rival": [fila(f, basico) for f in p["equipos"]["rival"]],
        "rival_linea": rival_linea(p.get("rival_linea")),
        "jungla": jungla(p.get("jungla")),
        "lineas": lineas(p.get("lineas") or [], p.get("gank"), modo),
        "historial": historial(p.get("historial")),
        "duelo": duelo(p.get("duelo")),
        # El plan es interpretación: solo antes de empezar a jugar (la app ya lo vacía en juego).
        "plan": list(p.get("plan") or []) if modo != "juego" else [],
        "avisos": [{"texto": a.get("texto", ""), "tono": a.get("tono", "")} for a in p.get("avisos") or []],
        "sin_avisos": "Esperando datos…" if c["cargando"] else "Nada que destacar.",
        "notas": notas(p.get("notas")),
        "reglas": list(p.get("recordatorios") or []),
        # Sin reglas (las de la partida propia), es la de otro jugador buscada a mano.
        "ajena": not p.get("recordatorios"),
    }


# --- pestaña Partida: selección de campeón y espera ------------------------------------------------------
def pool(pl: Mapping[str, Any] | None, pos: str | None) -> Json | None:
    """Tus opciones contra el campeón rival de tu posición. Son datos para elegir tú: no se marca ninguno."""
    if not pl:
        return {"vacio": f"Cuando el rival elija a alguien de {pos} verás aquí tus campeones contra él."} if pos else None
    filas = []
    for f in pl.get("filas") or []:
        if f.get("wr") is None:
            master: Json = {"linea2": f"{f['n']} partidas, pocas" if f.get("n") else "sin partidas"}
        else:
            master = {
                "wr": num(f"{f['wr']}%", "bien" if f["wr"] >= 53 else "mal" if f["wr"] <= 47 else ""),
                "barra": barra_wr(f["v"], f["n"]),
                "n": f["n"],
            }
        filas.append(
            {
                "retrato": imagen(f.get("icono")),
                "nombre": f.get("nombre", ""),
                "master": master,
                "yo": num(f"{f['yo_v']}V {f['yo_n'] - f['yo_v']}D") if f.get("yo_n") else con_tono("—", "suave"),
                "vs": num(f"{f['vs_v']}V {f['vs_n'] - f['vs_v']}D") if f.get("vs_n") else con_tono("—", "suave"),
            }
        )
    rival = pl.get("rival", "")
    return {
        "titulo": f"Tu pool contra {rival}",
        "sub": f"{pl.get('pos', '')} · partidas de Master+ y las tuyas de la temporada",
        "cabeza": ["Campeón", f"Master+ contra {rival}", "Tú con él", f"Tú contra {rival}"],
        "filas": filas,
        "vacio": "" if filas else f"No tienes campeones de {pl.get('pos', '')} con 5 partidas o más esta temporada.",
        "pie": "Ordenado por el % de Master+ (con 8 partidas o más). Son datos para decidir tú.",
    }


def seleccion(s: Mapping[str, Any]) -> Json:
    mio = s.get("mio")
    if s.get("basico"):
        return seleccion_basica(s)
    h = s.get("historial") or {}
    c = h.get("campeon") or {}
    if not mio:
        sub = "Cuando elijas campeón verás aquí tu historial con él."
    elif c.get("n"):
        sub = (
            num(f"{c['v']}V {c['n'] - c['v']}D")
            + f" con {esc(mio['nombre'])} esta temporada{esc(h.get('cola_txt', ''))} · "
            + num(f"{pct(c['v'], c['n'])}%", clase_wr(c["v"], c["n"]))
        )
    else:
        sub = f"Sin partidas con {esc(mio['nombre'])} esta temporada"
    pos = s.get("pos")
    que_se_ve = (
        "Solo campeones y tu historial contra ellos. "
        "En clasificatoria los nombres de tus aliados están ocultos y la app no intenta averiguarlos."
    )
    if pos and not s.get("duelo"):
        que_se_ve += f" Tu duelo de {pos} sale cuando el rival elija a alguien de esa posición."
    vs = h.get("vs") or []
    return {
        "hero": {
            "retrato": imagen(mio.get("icono")) if mio else "",
            "titulo": mio["nombre"] if mio else "Aún no has elegido",
            "sub": sub,
            "racha": racha(c.get("racha")),
        },
        "pool": pool(s.get("pool"), pos),
        "vs": {
            "sub": f"tus {h.get('n', 0)} clasificatorias{h.get('cola_txt', '')} de la temporada",
            "filas": filas_vs(vs, mio["nombre"] if mio else "") if vs else None,
            "vacio": "" if vs else "El rival aún no ha elegido.",
        },
        "duelo": duelo(s.get("duelo")),
        "notas": notas(s.get("notas")),
        "que_se_ve": que_se_ve,
        "elegir_rol": elegir_rol(s.get("rol")),
    }


def seleccion_basica(s: Mapping[str, Any]) -> Json:
    """La selección fuera de la Grieta (ARAM, Arena...): sin posiciones ni duelos; los rivales, en la pantalla de carga."""
    mio = s.get("mio")
    modo = s.get("modo", "")
    return {
        "hero": {
            "retrato": imagen(mio.get("icono")) if mio else "",
            "titulo": mio["nombre"] if mio else "Aún no has elegido",
            "sub": esc(f"{modo}: el panel con los diez sale en la pantalla de carga."),
            "racha": None,
        },
        "pool": None,
        "vs": {"sub": "", "filas": None, "vacio": f"En {modo} los rivales no se ven hasta la pantalla de carga."},
        "duelo": None,
        "notas": notas(s.get("notas")),
        "que_se_ve": f"En {modo} no hay posiciones: en la pantalla de carga verás el rango de cada jugador y su maestría "
        "con el campeón que lleva.",
        "elegir_rol": None,
    }


def espera(e: Mapping[str, Any]) -> Json:
    """Sin partida ni selección: qué hace la app y cómo sale el overlay (o que el modo de esta partida está apagado)."""
    sync = e.get("sync") or {}
    ov = e.get("overlay") or {}
    if e.get("apagada"):
        titulo = f"{e['apagada']}: sin panel"
        texto = (
            "Este modo está apagado en Ajustes, en Modos de juego: no salen el panel ni el overlay, y no se graba. "
            "El buscador de arriba sigue funcionando."
        )
    elif e.get("fase"):
        titulo, texto = e.get("fase_txt", ""), "En cuanto entres en partida, el panel se rellena solo."
    else:
        titulo = e.get("fase_txt", "")
        texto = "Abre el cliente del LoL. Mientras tanto puedes ver la partida de cualquier jugador con el buscador de arriba."
    return {
        "titulo": titulo,
        "texto": texto,
        "sync": (
            {
                "txt": "Descargando tu historial de la temporada · ",
                "num": f"{sync['hechas']} de {sync['total']}",
                "ancho": pct(sync["hechas"], sync["total"]) / 100,
            }
            if sync.get("total") and sync.get("hechas", 0) < sync["total"]
            else None
        ),
        "pasos": bool(ov.get("activo")) and not e.get("apagada"),
        "teclas": teclas(ov.get("atajo")),
        "aviso": ov.get("aviso") or "",
    }


# --- overlay -------------------------------------------------------------------------------------------------
def fila_overlay(f: Mapping[str, Any], basico: bool = False) -> Json:
    """Un jugador en el overlay. basico: fuera de la Grieta, su maestría con el campeón en vez de sus partidas."""
    muestra = f.get("muestra") or {}
    wr: Json = {"cargando": True}
    if basico:
        if f.get("maestria") is not None:
            wr = {"txt": miles(f["maestria"]), "tono": "", "linea2": "maestría"}
        elif f.get("oculto"):
            wr = {"txt": "—", "tono": "suave", "linea2": ""}
    elif muestra.get("n"):
        c = f.get("camp") or {}
        if c.get("n"):
            wr = {"txt": f"{c['v']}/{c['n']}", "tono": clase_wr(c["v"], c["n"]), "linea2": "campeón"}
        else:
            wr = {"txt": f"{muestra['v']}/{muestra['n']}", "tono": clase_wr(muestra["v"], muestra["n"]), "linea2": "últimas"}
    return {
        "soy_yo": bool(f.get("soy_yo")),
        "rol": rol(f.get("rol")),
        "retrato": imagen(f.get("icono")),
        "nombre": f.get("nombre", ""),
        "etiquetas": etiquetas(f.get("etiquetas") or [], 2),
        "campeon": f.get("campeon", ""),
        "rango": rango(f, compacto=True),
        "wr": wr,
    }


def overlay(e: Mapping[str, Any]) -> Json:
    """La ventana encima del juego: lo justo para leerlo en dos segundos. En partida, la app ya ha quitado lo que Riot
    no deja enseñar (plan, veredictos, duelo, mapa del jungla): aquí además no se piden."""
    p = e.get("panel")
    if not p:
        return {"esperando": True}
    modo = e.get("modo")
    basico = not p.get("completo", True)
    # Si no juegas jungla, tu rival de línea ocupa el sitio del jungla rival (su gank va en el plan).
    rl = p.get("rival_linea")
    j = p.get("jungla")
    ns = notas(p.get("notas"))
    avisos = p.get("avisos") or []
    if modo == "juego":
        destacado = {
            "titulo": "Datos destacados",
            "plan": [],
            "avisos": [{"texto": a.get("texto", ""), "tono": ""} for a in avisos[: max(1, 3 - len(ns))]],
        }
    else:
        destacado = {
            "titulo": "Antes de empezar",
            "plan": list(p.get("plan") or []),
            "avisos": [{"texto": a.get("texto", ""), "tono": a.get("tono", "")} for a in avisos[:2]],
        }
    destacado["notas"] = ns
    return {
        "esperando": False,
        "titulo": etapa(modo, p),
        "cola": p.get("cola", ""),
        "atajo": "Suelta" if modo == "juego" else "En partida, mantén",
        "teclas": teclas((e.get("overlay") or {}).get("atajo")),
        "basico": basico,
        "aliado": [fila_overlay(f, basico) for f in p["equipos"]["aliado"]],
        "rival": [fila_overlay(f, basico) for f in p["equipos"]["rival"]],
        "jungla": (
            {
                "titulo": f"Tu rival de línea · {rl.get('campeon', '')}",
                "sub": f"{rl.get('n', 0)} partidas de {NOMBRE_POS.get(rl.get('rol', ''), '')}"
                f" · {rl.get('n_lineas', 0)} líneas de tiempo",
                "tarjetas": tarjetas(rl, compacto=True),
            }
            if rl
            else {
                "titulo": f"Jungla rival · {j.get('campeon', '')}",
                "sub": f"{j.get('n', 0)} partidas · {j.get('n_lineas', 0)} líneas de tiempo",
                "tarjetas": tarjetas(j, compacto=True),
            }
            if j
            else None
        ),
        "duelo": duelo(p.get("duelo"), compacto=True) if modo != "juego" and p.get("duelo") else None,
        "destacado": destacado,
    }


# --- revisiones ----------------------------------------------------------------------------------------------
def hoy(lista: Sequence[Mapping[str, Any]], ahora: datetime | None = None) -> Json | None:
    """Lo de hoy: victorias, derrotas, LP y la racha (de la más antigua a la última). None si hoy no hay nada."""
    ahora = ahora or datetime.now()
    corte = ahora.replace(hour=HORA_CORTE, minute=0, second=0, microsecond=0)
    if ahora.hour < HORA_CORTE:
        corte -= timedelta(days=1)
    de_hoy = [x for x in lista if x["fecha"] >= corte.timestamp() * 1000]
    if not de_hoy:
        return None
    v = sum(1 for x in de_hoy if x["gana"])
    con_lp = [x["lp"] for x in de_hoy if x.get("lp") is not None]
    return {
        "v": v,
        "d": len(de_hoy) - v,
        "lp": lp(sum(con_lp)) if con_lp else None,
        "racha": [bool(x["gana"]) for x in reversed(de_hoy)],
    }


def item_lista(x: Mapping[str, Any]) -> Json:
    return {
        "id": x["id"],
        "gana": bool(x["gana"]),
        "campeon": x["campeon"],
        "kda": "/".join(str(n) for n in x["kda"]),
        "linea2": f"{fecha(x['fecha'])} · {x['duracion']}",
        "retrato": imagen(x.get("icono")),
        "lp": lp(x.get("lp")),
    }


def tendencia(nombre: str, filas: Sequence[Mapping[str, Any]] | None) -> Json | None:
    if not filas:
        return None
    return {
        "nombre": nombre,
        "filas": [
            {
                "nombre": f["nombre"],
                "barra": barra_wr(f["v"], f["n"]),
                "pct": f"{pct(f['v'], f['n'])}%",
                "tono": clase_wr(f["v"], f["n"]),
                "n": f["n"],
                "tip": f"{f['v']}V {f['n'] - f['v']}D",
            }
            for f in filas
        ],
    }


FILTROS_MUERTES = {"todas": "Todas", "antes": "<15 min", "despues": "15+ min", "derrotas": "Derrotas"}


def mapa_muertes(lista: Sequence[Mapping[str, Any]]) -> Json | None:
    """Tus muertes de las partidas revisadas, todas vistas desde la base azul, con los filtros ya hechos."""
    if not lista:
        return None

    def punto(m: Mapping[str, Any]) -> Json:
        return {
            "xy": en_mapa(m["x"], m["y"]),
            "id": m["id"],
            "tip": f"{m['campeon']} · {m['t']}",
            "tip2": f"ante {m['asesino']} · {'victoria' if m['gana'] else 'derrota'}",
        }

    filtros = {
        "todas": list(lista),
        "antes": [m for m in lista if m["ms"] < 15 * 60000],
        "despues": [m for m in lista if m["ms"] >= 15 * 60000],
        "derrotas": [m for m in lista if not m["gana"]],
    }
    return {
        "n": len(lista),
        "botones": [{"id": k, "txt": v} for k, v in FILTROS_MUERTES.items()],
        "puntos": {k: [punto(m) for m in v] for k, v in filtros.items()},
    }


def revisiones(datos: Mapping[str, Any], ahora: datetime | None = None) -> Json:
    lista = datos.get("lista") or []
    v = sum(1 for x in lista if x["gana"])
    t = datos.get("tendencias")
    return {
        "lista": [item_lista(x) for x in lista],
        "resumen": f"{v}V {len(lista) - v}D" if lista else "",
        "hoy": hoy(lista, ahora),
        "tendencias": (
            {
                "sub": f"{t['n']} clasificatorias de la temporada · barra = % de victorias, la marca es el 50%",
                "tablas": [
                    x
                    for x in (
                        tendencia("Sesión", t.get("sesion")),
                        tendencia("Hora", t.get("franjas")),
                        tendencia("Duración", t.get("duracion")),
                        tendencia("Contra tu rival de posición", t.get("rivales")),
                    )
                    if x
                ],
            }
            if t
            else None
        ),
        "muertes": mapa_muertes(datos.get("muertes") or []),
    }


def quien(o: Mapping[str, Any]) -> str:
    return ("tu equipo, contigo" if o.get("participaste") else "tu equipo, sin ti") if o.get("tuyo") else "rival"


def detalle(r: Mapping[str, Any], dif_oro: Sequence[int] | None) -> Json:
    """La revisión de una partida, con el gráfico de oro si se sabe la diferencia minuto a minuto."""
    liga_txt = liga(r["lp"]) if r.get("lp") else ""
    comp = r.get("comparacion")
    ref = r.get("referencia")
    return {
        "id": r["id"],
        "gana": bool(r["gana"]),
        "resultado": "Victoria" if r["gana"] else "Derrota",
        "campeon": r["campeon"],
        "duracion": r["duracion"],
        "retrato": imagen(r.get("icono")),
        "cabecera": " · ".join(t for t in (fecha(r["fecha"]), liga_txt) if t),
        "lp": lp((r.get("lp") or {}).get("cambio")),
        "grabacion": bool(r.get("carpeta")),
        "metricas": [
            {"que": "KDA", "kda": [str(n) for n in r["kda"]]},
            {"que": "CS/min", "v": coma(r["cs_min"])},
            {"que": "Part. en kills", "v": f"{r['kp']}%"},
            {"que": "Daño del equipo", "v": f"{r['dano_pct']}%"},
            {"que": "Visión", "v": str(r["vision"]), "sub": f"{r['wards']} wards · {r['control']} de control"},
        ],
        "grafico": oro.grafico(dif_oro, r["duracion"], r["objetivos"], r["muertes"]) if dif_oro else None,
        "muertes": [
            {
                "t": m["t"],
                "asesino": m["asesino"],
                "ayudas": ", ".join(m.get("ayudas") or []),
                "linea2": f"{m['donde']} · {m['rivales']} rival{'' if m['rivales'] == 1 else 'es'}",
                "perdido": m.get("perdido") or "",
                "clip": bool(m.get("clip")),
                "video": f"{m['video']['archivo']} · {m['video']['en']}" if not m.get("clip") and m.get("video") else "",
            }
            for m in r["muertes"]
        ],
        "comparacion": (
            {
                "rival": comp.get("rival", ""),
                "filas": [
                    {
                        "min": m,
                        "oro": diferencia(d["oro"][0], d["oro"][1]),
                        "cs": diferencia(d["cs"][0], d["cs"][1]),
                        "xp": diferencia(d["xp"][0], d["xp"][1]),
                        "nivel": diferencia(d["nivel"][0], d["nivel"][1]),
                    }
                    for m, d in (comp.get("minutos") or {}).items()
                ],
            }
            if comp
            else None
        ),
        "prevision": [
            {"tema": f["tema"], "dijo": f["dijo"], "paso": f["paso"], "acierto": bool(f["acierto"])}
            for f in r.get("prevision") or []
        ],
        "referencia": tabla_comparacion(ref, "Tú: esta partida.") if ref else None,
        "ref_titulo": f"Comparado con {ref['ref']}" if ref else "",
        "objetivos": [
            {"t": o["t"], "nombre": o["nombre"], "tuyo": bool(o["tuyo"]), "quien": quien(o)} for o in r.get("objetivos") or []
        ],
    }


# --- ajustes, novedades y demo ----------------------------------------------------------------------------
def ajustes(a: Mapping[str, Any]) -> Json:
    """El formulario de Ajustes con lo guardado."""
    campeones = list(a.get("campeones") or [])
    nombre_de = {str(c["id"]): c["nombre"] for c in campeones}
    partidas = a.get("referencias_partidas") or {}

    def estado_ref(cid: str) -> str:
        n = partidas.get(cid)
        if n is None:
            return ""
        return f"{n} partidas suyas con ese campeón" if n else "buscando sus partidas…"

    perfil = a.get("perfil_partidas")
    version = a.get("version") or {}
    modos = a.get("modos") or {}
    return {
        "rol": a.get("rol") or "JUNGLE",
        "roles": OPCIONES_ROL,
        "modos": [
            {"k": k, "v": nombre, "activo": modo_activo(modos, k), "nota": NOTA_MODO.get(k, "")} for k, nombre in MODOS.items()
        ],
        "overlay": bool(a.get("overlay")),
        "atajo": a.get("atajo_overlay", ""),
        "opacidad": math.floor((a.get("overlay_opacidad") or 0.94) * 100 + 0.5),
        "siempre": bool(a.get("siempre_en_marcha")),
        "grabar": bool(a.get("grabar")),
        "codificador": "cpu" if a.get("grabacion_codificador") == "cpu" else "auto",
        "max_gb": str(a.get("grabacion_max_gb") if a.get("grabacion_max_gb") is not None else 0),
        "cuentas": "\n".join(a.get("cuentas") or []),
        "reglas": "\n".join(a.get("recordatorios") or []),
        "comparar": [{"k": k, "v": v} for k, v in (a.get("opciones_comparar") or {}).items()],
        "comparar_con": a.get("comparar_con", ""),
        "perfil": a.get("perfil_base") or "",
        "perfil_estado": "" if perfil is None else f"{perfil} partidas suyas guardadas" if perfil else "buscando sus partidas…",
        "referencias": [
            {"campeon": nombre_de.get(str(cid), str(cid)), "texto": rid, "estado": estado_ref(str(cid))}
            for cid, rid in (a.get("referencias") or {}).items()
        ],
        "notas": [
            {"campeon": nombre_de.get(str(cid), str(cid)), "texto": txt, "estado": ""}
            for cid, txt in (a.get("notas") or {}).items()
        ],
        "campeones": sorted(c["nombre"] for c in campeones),
        "version": f"Deep Prep {version.get('version', '')}"
        + (
            f" · la {version.get('nueva', '')} se instala sola cuando cierres esta ventana, fuera de partida"
            if version.get("lista")
            else ""
        ),
    }


def leer_filas(filas: Sequence[Sequence[str]], campeones: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Notas y referencias por campeón de las filas del formulario: {id del campeón: texto}. Las filas sin campeón
    conocido o sin texto no cuentan."""
    out: dict[str, str] = {}
    por_nombre = {str(c["nombre"]).lower(): c["id"] for c in campeones}
    for nombre, texto in filas:
        cid = por_nombre.get(str(nombre).strip().lower())
        if cid is not None and str(texto).strip():
            out[str(cid)] = str(texto).strip()
    return out


def novedades(n: Mapping[str, Any] | None) -> Json | None:
    """Notas de la versión: las líneas que empiezan por '-', '*' o '•' son puntos; el resto, párrafos."""
    if not n:
        return None
    lineas = [l.strip() for l in str(n.get("notas") or "").split("\n") if l.strip()]
    return {
        "version": n.get("version", ""),
        "parrafos": [re.sub(r"^#+\s*", "", l) for l in lineas if not re.match(r"^[-*•]", l)],
        "puntos": [re.sub(r"^[-*•]\s*", "", l) for l in lineas if re.match(r"^[-*•]", l)],
    }


# En el orden de una partida. Las tres primeras son de la partida de ejemplo (las cambia la app, y con ellas el
# overlay); Revisiones y Ajustes son pestañas. overlay: la escena también sale encima del juego.
ESCENAS: list[Json] = [
    {
        "id": "seleccion",
        "nombre": "Selección de campeón",
        "vista": "partida",
        "overlay": False,
        "txt": "Antes de elegir: tu duelo en partidas de Master+, tu pool contra el rival "
        "y tu historial contra lo que van eligiendo.",
    },
    {
        "id": "carga",
        "nombre": "Pantalla de carga",
        "vista": "partida",
        "overlay": True,
        "txt": "Mientras carga: los diez jugadores, el jungla rival y su mapa, y dónde va a haber errores. "
        "También sale encima del juego.",
    },
    {
        "id": "juego",
        "nombre": "En partida",
        "vista": "partida",
        "overlay": True,
        "txt": "Ya jugando, solo datos de antes de empezar: sin plan, sin veredictos ni mapa del jungla, "
        "como piden las normas de Riot.",
    },
    {
        "id": "revisiones",
        "nombre": "Revisiones",
        "vista": "revisiones",
        "overlay": False,
        "txt": "Al acabar: la partida minuto a minuto, dónde mueres y qué acertó o falló el panel.",
    },
    {
        "id": "ajustes",
        "nombre": "Ajustes",
        "vista": "ajustes",
        "overlay": False,
        "txt": "Se pueden cambiar y guardar: en la demo van a una carpeta temporal que se borra al cerrar.",
    },
]


def escena_actual(demo: Mapping[str, Any], vista: str) -> str:
    """La escena que se está viendo: la pestaña abierta o, en Partida, la de la partida de ejemplo."""
    return str(demo.get("escena", "")) if vista == "partida" else vista


# --- lo común a todas las pestañas --------------------------------------------------------------------------
def comun(e: Mapping[str, Any]) -> Json:
    """Barra lateral (estado, cuenta, consultas a Riot, grabación), aviso de la clave y de la versión nueva."""
    fase = e.get("fase")
    g = e.get("grabacion")
    cuota = e.get("cuota") or {}
    usadas = pct(cuota.get("usadas", 0), cuota.get("tope", 0))
    v = e.get("version") or {}
    clave = e.get("clave") or {"ok": True}
    return {
        "fase": {"txt": e.get("fase_txt", ""), "tono": "vivo" if fase == "InProgress" else "activo" if fase else ""},
        "grabacion": (
            {
                "txt": "Grabación parada" if g.get("parada") else "Grabando" if g.get("carpeta") else "Grabación lista",
                "tono": "parada" if g.get("parada") else "rec" if g.get("carpeta") else "",
                "tip": "El vídeo ha dejado de crecer"
                if g.get("parada")
                else g.get("carpeta") or "Esperando a que arranque el juego",
            }
            if g
            else None
        ),
        "cuenta": e.get("cuenta") or "",
        "cuota": {"txt": f"{cuota.get('usadas', 0)}/{cuota.get('tope', 0)}", "ancho": usadas / 100, "lleno": usadas >= 90},
        "clave": None if clave.get("ok") else clave.get("error") or "",
        "ultima_revision": e.get("ultima_revision"),
        "version": v.get("nueva") if v.get("lista") else None,
        "novedades": novedades(e.get("novedades")),
        "demo": e.get("demo"),
    }


def partida(e: Mapping[str, Any]) -> Json:
    """Qué enseña la pestaña Partida con este estado: el panel, la selección de campeón o la espera."""
    p = e.get("panel")
    s = e.get("seleccion")
    if p and (not s or not p.get("terminada")):
        return {"vista": "panel", "datos": panel(e)}
    if s:
        return {"vista": "seleccion", "datos": seleccion(s)}
    return {"vista": "espera", "datos": espera(e)}
