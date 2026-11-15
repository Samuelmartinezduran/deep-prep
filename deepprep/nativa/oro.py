"""El gráfico de la partida: la diferencia de oro entre los dos equipos, minuto a minuto.

La diferencia la guarda cada revisión (revision.revisar, «dif_oro»: un valor por fotograma de la línea de tiempo, al
empezar cada minuto y al acabar). Aquí se prepara para pintarla: tramos, áreas, escala y textos, todo en unidades de
la partida (minutos y oro); la interfaz solo lo escala a píxeles.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

Punto = tuple[float, float]  # (minuto, oro de tu equipo menos el del rival)

# Pasos posibles de la escala del oro: el menor con el que la escala entera cabe en TRAMOS tramos o menos.
PASOS = (500, 1000, 2000, 2500, 5000, 10_000, 20_000)
TRAMOS = 4


def minutos(t: str) -> float:
    """'14:53' -> 14.88."""
    m, _, s = str(t or "0:0").partition(":")
    try:
        return int(m or 0) + int(s or 0) / 60
    except ValueError:
        return 0.0


def puntos(dif: Sequence[int], duracion_min: float) -> list[Punto]:
    """Un punto por fotograma: uno al empezar cada minuto y el último al acabar la partida."""
    pts: list[Punto] = [(float(i), float(v)) for i, v in enumerate(dif)]
    if len(pts) > 1 and 0 < duracion_min < pts[-1][0]:
        pts[-1] = (duracion_min, pts[-1][1])
    return pts


def tramos(pts: Sequence[Punto]) -> tuple[list[list[Punto]], list[list[Punto]]]:
    """La curva partida en tramos por encima y por debajo de 0, que se cortan justo en el 0 (interpolado).

    Así cada tramo se pinta de un color sin que el de un equipo invada el lado del otro.
    """
    arriba: list[list[Punto]] = []
    abajo: list[list[Punto]] = []
    actual: list[Punto] = []
    signo = 0
    for t, v in pts:
        s = (v > 0) - (v < 0)
        if actual and s and signo and s != signo:
            t0, v0 = actual[-1]
            corte = (t0 + (t - t0) * v0 / (v0 - v), 0.0)
            actual.append(corte)
            (arriba if signo > 0 else abajo).append(actual)
            actual = [corte]
        if s:
            signo = s
        actual.append((t, v))
    if actual:
        (arriba if signo >= 0 else abajo).append(actual)
    return arriba, abajo


def areas(tramos_: Iterable[Sequence[Punto]]) -> list[list[Punto]]:
    """Cada tramo cerrado contra el 0: el polígono que se rellena."""
    return [[(tr[0][0], 0.0), *tr, (tr[-1][0], 0.0)] for tr in tramos_ if len(tr) > 1]


def escala(minimo: float, maximo: float) -> tuple[int, int, int]:
    """(abajo, arriba, paso) del eje del oro. No es simétrica: se ajusta a la partida (una partida que se fue a −11k
    no deja medio gráfico vacío por arriba), pero el 0 siempre queda dentro, con al menos un paso a cada lado."""

    def con(paso: int) -> tuple[int, int, int]:
        return min(-paso, math.floor(min(minimo, 0) / paso) * paso), max(paso, math.ceil(max(maximo, 0) / paso) * paso), paso

    for paso in PASOS:
        abajo, arriba, _ = con(paso)
        if (arriba - abajo) / paso <= TRAMOS:
            return abajo, arriba, paso
    return con(PASOS[-1])  # una partida de más de 80k de diferencia: con más tramos


def k(v: float, signo: bool = True) -> str:
    """12400 -> '+12,4k'; -800 -> '−0,8k'; 0 -> '0'. Con el menos tipográfico, como el resto del panel."""
    if round(v) == 0:
        return "0"
    miles = abs(v) / 1000
    txt = f"{miles:.1f}".rstrip("0").rstrip(".").replace(".", ",") + "k"
    if not signo:
        return txt
    return ("+" if v > 0 else "−") + txt


def grafico(
    dif: Sequence[int], duracion: str, objetivos: Sequence[Mapping[str, Any]], muertes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Todo lo que pinta el gráfico de la partida, en unidades de la partida.

    objetivos y muertes: los de la revisión (con su minuto como 'm:ss'), para las marcas y el detalle al pasar el ratón.
    """
    fin = max(minutos(duracion), 1.0)
    pts = puntos(dif, fin)
    if pts:
        fin = max(fin, pts[-1][0])
    valores = [v for _, v in pts] or [0.0]
    abajo, arriba, paso = escala(min(valores), max(valores))
    por_delante, por_detras = tramos(pts)
    ultimo = pts[-1][1] if pts else 0.0
    return {
        "fin": fin,
        "abajo": abajo,
        "arriba": arriba,
        "marcas_y": [{"v": v, "txt": k(v)} for v in range(arriba, abajo - 1, -paso)],
        "marcas_x": list(range(0, int(fin) + 1, 5)),
        "puntos": [[t, v, k(v)] for t, v in pts],  # con su texto, para el detalle al pasar el ratón
        "tramos_arriba": [[[t, v] for t, v in tr] for tr in por_delante],
        "tramos_abajo": [[[t, v] for t, v in tr] for tr in por_detras],
        "areas_arriba": [[[t, v] for t, v in a] for a in areas(por_delante)],
        "areas_abajo": [[[t, v] for t, v in a] for a in areas(por_detras)],
        "final": {"v": ultimo, "txt": k(ultimo)},
        "objetivos": [
            {
                "t": minutos(o["t"]),
                "txt": o["t"],
                "nombre": o["nombre"],
                "tuyo": bool(o["tuyo"]),
                "participaste": bool(o.get("participaste")),
            }
            for o in objetivos
        ],
        "muertes": [
            {
                "t": minutos(m["t"]),
                "txt": m["t"],
                "asesino": m["asesino"],
                "cara": bool(m.get("perdido")),
                "perdido": m.get("perdido") or "",
            }
            for m in muertes
        ],
    }
