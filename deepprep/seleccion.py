"""La selección de campeón: tu duelo, tu pool contra su campeón, tu historial y tus notas, antes de empezar."""

import time
from collections.abc import Callable, Collection, Iterable

from . import analisis as an
from .comparador import Comparador
from .constantes import MODOS, MODOS_GRIETA, NOMBRE_LIGA, modo_de
from .ddragon import Datos
from .lcu import Cliente as ClienteLoL
from .partidas import Partidas
from .tipos import Json


class Seleccion:
    """Lo que enseña el panel durante la selección de campeón (actual), leído del cliente del LoL.

    cuentas: tus cuentas (puuid -> 'Nombre#TAG'). notas_de(campeones, rivales): tus notas de esos campeones.
    rol_de_hoy(con_smite, inferido): tu posición en esta partida y por qué (App.rol_de_hoy). al_empezar(): se llama al
    empezar cada selección (lo que eligieras a mano en la anterior ya no vale).
    """

    def __init__(
        self,
        lcu: ClienteLoL,
        datos: Datos,
        cuentas: dict[str, str],
        partidas: Partidas,
        comparador: Comparador,
        notas_de: Callable[[Iterable[int], Collection[int]], list[Json]],
        rol_de_hoy: Callable[[bool | None, str], tuple[str, str]] = lambda con_smite, inferido: ("", ""),
        al_empezar: Callable[[], None] = lambda: None,
    ) -> None:
        self.lcu = lcu
        self.datos = datos
        self.cuentas = cuentas
        self.partidas = partidas
        self.comparador = comparador
        self.notas_de = notas_de
        self.rol_de_hoy = rol_de_hoy
        self.al_empezar = al_empezar
        self.actual: Json | None = None
        self._clave: tuple[int, tuple[int, ...], int, str] | None = None
        self._abierta = False
        # La posición que te tocó en la última selección ('' si la cola no la da): sigue valiendo ya en la partida.
        self.pos_asignada = ""

    def cerrar(self) -> None:
        """Ya no hay selección (se ha salido de ella o el cliente está cerrado)."""
        self.actual = None
        self._abierta = False

    def releer(self) -> None:
        """Ha cambiado algo de fuera (tu rol de hoy): se vuelve a montar aunque la selección no haya cambiado."""
        self._clave = None
        self.leer()

    def leer(self) -> Json | None:
        """Lee la selección del cliente; si no ha cambiado desde la última vez, se queda con lo que ya había."""
        self.actual = self._leer()
        return self.actual

    def _leer(self) -> Json | None:
        s = self.lcu.seleccion()
        if not s:
            return None
        if not self._abierta:
            self._abierta = True
            self.al_empezar()
        self.pos_asignada = s.get("pos", "")
        modo = modo_de(s["cola"], s.get("mapa", 0))
        completo = modo in MODOS_GRIETA
        # Los hechizos aún pueden cambiar: en la selección no corrigen tu posición (ya en partida, sí).
        pos, motivo = self.rol_de_hoy(None, "") if completo else ("", "")
        clave = (s["mio"], tuple(s["rivales"]), s["cola"], pos)
        if clave == self._clave and self.actual:
            return self.actual
        self._clave = clave
        datos = self.datos
        mio = (
            {"nombre": datos.nombre(s["mio"]), "icono": datos.icono(s["mio"]), "splash": datos.splash(s["mio"])}
            if s["mio"]
            else None
        )
        rol = {"actual": pos, "motivo": an.MOTIVOS_ROL.get(motivo, ""), "elegible": completo}
        if not completo:
            # Fuera de la Grieta no hay posiciones ni duelos: tu campeón y tus notas (los rivales salen en la carga).
            vacio = {"duelo": None, "pool": None, "historial": None, "pos": ""}
            return {**vacio, "basico": True, "modo": MODOS[modo], "rol": rol, "mio": mio, "notas": self.notas_de([s["mio"]], ())}
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
            "rol": rol,
            "basico": False,
            "mio": mio,
            "historial": h,
            "notas": self.notas_de([s["mio"], *s["rivales"]], set(s["rivales"])),
        }
