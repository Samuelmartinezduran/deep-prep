"""Tus duelos medidos en partidas de Master+ y con quién se comparan tus números (tu referencia)."""

import time
from typing import Any

from . import analisis as an
from . import duelos as du
from . import recolector as rec
from .riot import ErrorRiot

# Con quién se comparan tus números en el duelo y en la revisión (ajuste "comparar_con").
COMPARAR_CON = {
    "perfil": "Un jugador (tu perfil de referencia)",
    "ganan": "Los que ganan este duelo",
    "challenger": "Challenger",
    "gm": "Gran Maestro o más",
    "mis_victorias": "Tus victorias",
}
# Un duelo ya calculado vale este rato (el panel lo pide a cada momento).
DURACION_DUELO_S = 120


class Comparador:
    """El duelo de tu campeón contra su rival, tu pool contra un campeón y tus jugadores de referencia.

    cfg: la configuración en uso (la de Configuracion.valores). cuentas: tus cuentas (puuid -> 'Nombre#TAG').
    """

    def __init__(self, cfg, duelos, cliente, datos, cuentas, partidas):
        self.cfg = cfg
        self.duelos = duelos
        self.cliente = cliente
        self.datos = datos
        self.cuentas = cuentas
        self.partidas = partidas
        self._hechos: dict[tuple[int, str, int], tuple[float, dict[str, Any]]] = {}

    def olvidar(self):
        """Los ajustes han cambiado (con quién te comparas): los duelos ya calculados no valen."""
        self._hechos.clear()

    # --- duelos de Master+ ---------------------------------------------------------------------
    def duelo(self, a, pos, b):
        """Tu campeón contra su rival directo: lo que dicen las partidas de Master+ y tus números al lado."""
        if not (a and b and pos):
            return None
        clave = (a, pos, b)
        hecho = self._hechos.get(clave)
        if hecho and time.time() - hecho[0] < DURACION_DUELO_S:
            return hecho[1]
        mias = set(self.cuentas)
        registros = self.duelos.duelo(a, pos, b, excluir=mias)
        res = du.analizar(registros, [], self.datos.nombre(a), self.datos.nombre(b), pos, self.datos.objeto, self.datos.runa)
        ref, nombre_ref = self.referencia(a, pos, b, registros)
        res["tu"] = du.comparar(
            self.duelos.de(mias, a, pos), ref, pos, nombre_ref, minimo=3 if nombre_ref != "Ganan este duelo" else du.MIN_GRUPO
        )
        res.update(
            {
                "a": self.datos.nombre(a),
                "b": self.datos.nombre(b),
                "icono_a": self.datos.icono(a),
                "icono_b": self.datos.icono(b),
                "pos": an.NOMBRE_POS.get(pos, pos),
                "en_pool": (a, pos) in set(self.partidas.pool()),
            }
        )
        self._hechos[clave] = (time.time(), res)
        return res

    def pool_contra(self, pos, rival, cola=None):
        """Tu pool de esa posición contra el campeón rival (selección de campeón)."""
        if not (pos and rival):
            return None
        mias = set(self.cuentas)
        pool = [(a, p) for a, p in self.partidas.pool() if p == pos]
        if not pool:
            return None
        registros = {a: self.duelos.duelo(a, pos, rival, excluir=mias) for a, _ in pool}
        filas = an.pool_contra(pool, pos, rival, registros, self.partidas.mis_partidas(cola), mias, du.MIN_GRUPO)
        for f in filas:
            f.update(nombre=self.datos.nombre(f["campeon"]), icono=self.datos.icono(f["campeon"]))
        return {
            "rival": self.datos.nombre(rival),
            "icono_rival": self.datos.icono(rival),
            "pos": an.NOMBRE_POS.get(pos, pos),
            "filas": filas,
        }

    # --- jugadores de referencia ------------------------------------------------------------------
    def resolver_referencia(self, rid):
        """Busca la cuenta y su servidor; devuelve un texto de error o ''."""
        if self.duelos.kv_get(f"ref:{rid.lower()}"):
            return ""
        nombre, _, tag = rid.partition("#")
        if not nombre or not tag:
            return f"{rid}: las referencias van como Nombre#TAG."
        try:
            cuenta = self.cliente.cuenta_por_riot_id(nombre.strip(), tag.strip())
            if not cuenta:
                return f"No encuentro la cuenta {rid}."
            plataforma = (
                self.cliente._get(self.cliente.region, f"/riot/account/v1/region/by-game/lol/by-puuid/{cuenta['puuid']}") or {}
            ).get("region", "")
        except ErrorRiot as e:
            return f"No pude buscar {rid}: {e}"
        if plataforma.lower() not in rec.REGION_DE:
            return f"No sé en qué servidor juega {rid}."
        self.duelos.kv_set(
            f"ref:{rid.lower()}",
            {
                "puuid": cuenta["puuid"],
                "plataforma": plataforma.lower(),
                "rid": f"{cuenta.get('gameName', nombre)}#{cuenta.get('tagLine', tag)}",
            },
        )
        return ""

    def para_el_recolector(self):
        """Los jugadores de referencia con su región y el campeón con el que te comparas (None en el perfil de base:
        interesan todas sus partidas)."""
        pares: list[tuple[int | None, str]] = [(int(c), rid) for c, rid in (self.cfg.get("referencias") or {}).items()]
        if self.cfg.get("comparar_con") == "perfil" and self.cfg.get("perfil_base"):
            pares.append((None, self.cfg["perfil_base"]))
        out = []
        for campeon, rid in pares:
            info = self.duelos.kv_get(f"ref:{rid.lower()}")
            if info:
                out.append({"puuid": info["puuid"], "region": rec.REGION_DE[info["plataforma"]], "campeon": campeon})
        return out

    def partidas_de_referencias(self):
        """Para los ajustes: ({campeón: partidas guardadas de su referencia}, partidas guardadas del perfil de base)."""
        partidas = {}
        for campeon, rid in (self.cfg.get("referencias") or {}).items():
            info = self.duelos.kv_get(f"ref:{rid.lower()}")
            partidas[campeon] = len(self.duelos.de({info["puuid"]}, int(campeon), None)) if info else None
        perfil = self.cfg.get("perfil_base")
        info = self.duelos.kv_get(f"ref:{perfil.lower()}") if perfil else None
        perfil_partidas = len(self.duelos.vistas_de(info["puuid"])) if info else None
        return partidas, perfil_partidas

    def referencia(self, a, pos, b, registros=None):
        """(registros de tu referencia, cómo se llama) para comparar tus números con ese campeón y posición."""
        rid = (self.cfg.get("referencias") or {}).get(str(a))
        if rid:
            info = self.duelos.kv_get(f"ref:{rid.lower()}") or {}
            nombre = (info.get("rid") or rid).split("#")[0]
            suyos = self.duelos.campeon(a, pos, {info.get("puuid")})
            contra = [r for r in suyos if r["b"] == b]
            return (contra, f"{nombre} contra {self.datos.nombre(b)}") if len(contra) >= 5 else (suyos, nombre)
        modo = self.cfg.get("comparar_con", "ganan")
        mias = set(self.cuentas)
        perfil = self.cfg.get("perfil_base")
        if modo == "perfil" and perfil:
            # Tu perfil de base: con tu campeón si lo juega; si no, en tu posición con lo que juegue.
            info = self.duelos.kv_get(f"ref:{perfil.lower()}") or {}
            nombre = (info.get("rid") or perfil).split("#")[0]
            suyos = self.duelos.campeon(a, pos, {info.get("puuid")})
            if len(suyos) >= 3:
                contra = [r for r in suyos if r["b"] == b]
                return (
                    (contra, f"{nombre} contra {self.datos.nombre(b)}")
                    if len(contra) >= 5
                    else (suyos, f"{nombre} con {self.datos.nombre(a)}")
                )
            en_pos = self.duelos.posicion(pos, {info.get("puuid")})
            if len(en_pos) >= 3:
                return en_pos, f"{nombre} de {an.NOMBRE_POS.get(pos, pos)}"
            modo = "ganan"  # aún sin partidas suyas en esa posición
        if modo == "mis_victorias":
            return [r for r in self.duelos.de(mias, a, pos) if r["g"]], "Tus victorias"
        if modo in ("challenger", "gm"):
            niveles = {"challenger": ("CHALLENGER",), "gm": ("CHALLENGER", "GRANDMASTER")}[modo]
            de_nivel = {p for p, n in self.duelos.niveles().items() if n in niveles}
            return self.duelos.campeon(a, pos, de_nivel - mias), COMPARAR_CON[modo]
        if registros is None:
            registros = self.duelos.duelo(a, pos, b, excluir=mias)
        return [r for r in registros if r["g"]], "Ganan este duelo"
