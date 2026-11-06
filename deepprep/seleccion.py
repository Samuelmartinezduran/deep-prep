"""La selección de campeón: tu duelo, tu pool contra su campeón, tu historial y tus notas, antes de empezar."""

import time
from collections.abc import Callable, Collection, Iterable

from . import analisis as an
from .comparador import Comparador
from .constantes import NOMBRE_LIGA
from .ddragon import Datos
from .lcu import Cliente as ClienteLoL
from .partidas import Partidas
from .tipos import Json


class Seleccion:
    """Lo que enseña el panel durante la selección de campeón (actual), leído del cliente del LoL.

    cuentas: tus cuentas (puuid -> 'Nombre#TAG'). notas_de(campeones, rivales): tus notas de esos campeones.
    """

    def __init__(
        self,
        lcu: ClienteLoL,
        datos: Datos,
        cuentas: dict[str, str],
        partidas: Partidas,
        comparador: Comparador,
        notas_de: Callable[[Iterable[int], Collection[int]], list[Json]],
    ) -> None:
        self.lcu = lcu
        self.datos = datos
        self.cuentas = cuentas
        self.partidas = partidas
        self.comparador = comparador
        self.notas_de = notas_de
        self.actual: Json | None = None
        self._clave: tuple[int, tuple[int, ...], int, str] | None = None

    def cerrar(self) -> None:
        """Ya no hay selección (se ha salido de ella o el cliente está cerrado)."""
        self.actual = None

    def leer(self) -> Json | None:
        """Lee la selección del cliente; si no ha cambiado desde la última vez, se queda con lo que ya había."""
        self.actual = self._leer()
        return self.actual

    def _leer(self) -> Json | None:
        s = self.lcu.seleccion()
        if not s:
            return None
        clave = (s["mio"], tuple(s["rivales"]), s["cola"], s.get("pos", ""))
        if clave == self._clave and self.actual:
            return self.actual
        self._clave = clave
        datos = self.datos
        pos = s.get("pos", "")
        rival = an.rival_probable(s["rivales"], pos, datos.roles) if pos else None
        rivales = [{"campeon": c, "pos": pos if c == rival else "", "nombre_campeon": datos.nombre(c)} for c in s["rivales"]]
        h = an.mi_historial(
            set(self.cuentas), self.partidas.mis_partidas(s["cola"]), s["mio"], rivales, {}, int(time.time() * 1000), mi_pos=pos
        )
        h["cola_txt"] = NOMBRE_LIGA.get(s["cola"], "")
        for fila in h["vs"]:
            fila["icono"] = datos.icono(fila["campeon"])
        return {
            "duelo": self.comparador.duelo(s["mio"], pos, rival) if s["mio"] and rival else None,
            "pool": self.comparador.pool_contra(pos, rival, s["cola"]),
            "pos": an.NOMBRE_POS.get(pos, ""),
            "mio": {"nombre": datos.nombre(s["mio"]), "icono": datos.icono(s["mio"]), "splash": datos.splash(s["mio"])}
            if s["mio"]
            else None,
            "historial": h,
            "notas": self.notas_de([s["mio"], *s["rivales"]], set(s["rivales"])),
        }
