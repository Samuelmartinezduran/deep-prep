"""Lo que se cambia desde los ajustes del panel: qué se puede tocar, cómo se comprueba y tus notas por campeón."""

from collections.abc import Callable, Collection, Iterable
from typing import TYPE_CHECKING, Any, Protocol

from .comparador import COMPARAR_CON
from .config import Configuracion
from .ddragon import Datos
from .overlay import parsear_atajo
from .tipos import Json, Resultado

if TYPE_CHECKING:
    from .actualizador import Actualizador

# Lo que el panel puede leer y cambiar de config.json.
EDITABLES = (
    "cuentas",
    "recordatorios",
    "notas",
    "grabar",
    "overlay",
    "atajo_overlay",
    "overlay_opacidad",
    "siempre_en_marcha",
    "comparar_con",
    "referencias",
    "perfil_base",
    "grabacion_codificador",
    "grabacion_max_gb",
)


class Referencias(Protocol):
    """Lo que los ajustes piden al comparador (comparador.Comparador; en la demo, uno que no pregunta a Riot)."""

    def resolver_referencia(self, rid: str) -> str: ...

    def partidas_de_referencias(self) -> tuple[dict[str, int | None], int | None]: ...


class _Rechazo(Exception):
    """Un ajuste que no vale; el texto es lo que se le dice a quien lo ha escrito."""


# --- cómo se comprueba y se limpia cada ajuste (lanzan _Rechazo, o TypeError/ValueError con un formato raro) -----
def _cuentas(valor: Iterable[Any]) -> list[str]:
    cuentas = [str(c).strip() for c in valor if str(c).strip()]
    if not cuentas or any("#" not in c for c in cuentas):
        raise _Rechazo("Las cuentas van como Nombre#TAG, y al menos una.")
    return cuentas


def _recordatorios(valor: Iterable[Any]) -> list[str]:
    return [str(r).strip()[:160] for r in valor if str(r).strip()][:8]


def _notas(valor: Any) -> dict[str, str]:
    return {str(int(k)): str(v).strip()[:300] for k, v in dict(valor).items() if str(v).strip()}


def _comparar_con(valor: Any) -> str:
    if valor not in COMPARAR_CON:
        raise _Rechazo("Esa referencia no existe.")
    return str(valor)


def _codificador(valor: Any) -> str:
    if valor not in ("auto", "cpu"):
        raise _Rechazo("Codificador desconocido.")
    return str(valor)


def _max_gb(valor: Any) -> int:
    return max(0, int(float(valor or 0)))


def _atajo(valor: Any) -> str:
    if not parsear_atajo(str(valor)):
        raise _Rechazo("No entiendo ese atajo. Ejemplos: ctrl+tab, alt+x, f9.")
    return str(valor).strip().lower()


def _opacidad(valor: Any) -> float:
    return min(1.0, max(0.4, float(valor)))


class Ajustes:
    """Lee y guarda los ajustes del panel.

    arranque_windows(encendido) pone o quita el arranque con Windows y devuelve un texto de error o ''.
    al_guardar(nuevo) se llama con lo que ha cambiado, ya guardado, para que la app lo aplique.
    """

    def __init__(
        self,
        configuracion: Configuracion,
        datos: Datos,
        comparador: Referencias,
        actualizador: "Actualizador",
        arranque_windows: Callable[[bool], str],
        al_guardar: Callable[[Json], None],
    ) -> None:
        self.configuracion = configuracion
        self.cfg = configuracion.valores
        self.datos = datos
        self.comparador = comparador
        self.actualizador = actualizador
        self.arranque_windows = arranque_windows
        self._al_guardar = al_guardar

    def leer(self) -> Json:
        por_nombre = sorted(self.datos.campeones.items(), key=lambda par: par[1]["nombre"])
        campeones = [{"id": i, "nombre": c["nombre"]} for i, c in por_nombre]
        partidas, perfil_partidas = self.comparador.partidas_de_referencias()
        return {
            **{k: self.cfg.get(k) for k in EDITABLES},
            "campeones": campeones,
            "opciones_comparar": COMPARAR_CON,
            "referencias_partidas": partidas,
            "perfil_partidas": perfil_partidas,
            "version": self.actualizador.estado,
        }

    def guardar(self, cambios: Any) -> Resultado:
        try:
            nuevo = self._validar(cambios)
        except _Rechazo as e:
            return {"ok": False, "error": str(e)}
        except (TypeError, ValueError):
            return {"ok": False, "error": "Algún valor no tiene el formato esperado."}
        if "siempre_en_marcha" in nuevo and nuevo["siempre_en_marcha"] != self.cfg.get("siempre_en_marcha"):
            error = self.arranque_windows(nuevo["siempre_en_marcha"])
            if error:
                return {"ok": False, "error": error}
        self.cfg.update(nuevo)
        self.configuracion.guardar()
        self._al_guardar(nuevo)
        return {"ok": True}

    def _validar(self, cambios: Any) -> Json:
        """Lo que cambia, ya comprobado y limpio. Se mira en este orden y el primer ajuste que no vale es el que se dice."""
        primero: tuple[tuple[str, Callable[[Any], Any]], ...] = (
            ("cuentas", _cuentas),
            ("recordatorios", _recordatorios),
            ("notas", _notas),
            ("grabar", bool),
            ("overlay", bool),
            ("siempre_en_marcha", bool),
            ("comparar_con", _comparar_con),
            ("perfil_base", self._perfil_base),
        )
        despues: tuple[tuple[str, Callable[[Any], Any]], ...] = (
            ("referencias", self._referencias),
            ("grabacion_codificador", _codificador),
            ("grabacion_max_gb", _max_gb),
            ("atajo_overlay", _atajo),
            ("overlay_opacidad", _opacidad),
        )
        nuevo: dict[str, Any] = {}
        for clave, validar in primero:
            if clave in cambios:
                nuevo[clave] = validar(cambios[clave])
        # Antes de buscar las referencias: sin el jugador con quien compararte no hace falta buscar nada.
        if (nuevo.get("comparar_con") or self.cfg.get("comparar_con")) == "perfil" and not nuevo.get(
            "perfil_base", self.cfg.get("perfil_base")
        ):
            raise _Rechazo("Para compararte con un jugador, escribe su Nombre#TAG en el perfil de referencia.")
        for clave, validar in despues:
            if clave in cambios:
                nuevo[clave] = validar(cambios[clave])
        return nuevo

    def _perfil_base(self, valor: Any) -> str:
        perfil = str(valor).strip()
        if perfil:
            self._buscar_referencia(perfil)
        return perfil

    def _referencias(self, valor: Any) -> dict[str, str]:
        refs: dict[str, str] = {}
        for campeon, rid in dict(valor).items():
            rid = str(rid).strip()
            if not rid:
                continue
            self._buscar_referencia(rid)
            refs[str(int(campeon))] = rid
        return refs

    def _buscar_referencia(self, rid: str) -> None:
        """Busca la cuenta de referencia (y su servidor) y la apunta; si no se puede, ese ajuste no vale."""
        error = self.comparador.resolver_referencia(rid)
        if error:
            raise _Rechazo(error)

    def notas_de(self, campeones: Iterable[int], rivales: Collection[int] = ()) -> list[Json]:
        """Tus notas de los campeones que hay en la partida (las escribiste tú antes de jugar)."""
        notas = self.cfg.get("notas") or {}
        vistos: set[int] = set()
        out: list[Json] = []
        for c in campeones:
            if c and c not in vistos and notas.get(str(c)):
                vistos.add(c)
                out.append(
                    {"campeon": self.datos.nombre(c), "icono": self.datos.icono(c), "texto": notas[str(c)], "rival": c in rivales}
                )
        return out
