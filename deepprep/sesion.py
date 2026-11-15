"""Una partida en vivo: pide los datos de los diez jugadores y monta el panel."""

import threading
import time
from collections import Counter
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from . import analisis as an
from .constantes import COLAS, COLAS_GRIETA, FLEXIBLE, GRIETA, LIGA_COLA, MODOS, MODOS_GRIETA, NOMBRE_LIGA, SOLO_DUO, modo_de
from .tipos import Aviso, Etiqueta, Json, LigaUI, Linea, Panel, Partida

if TYPE_CHECKING:
    from .app import App

Filas = dict[str | int, Json]  # puuid (o id() si el perfil está oculto) -> datos de trabajo del jugador
PorPosicion = dict[str, dict[str, Json]]  # 'aliado'|'rival' -> {posición: jugador}
AvisoConPeso = tuple[int, str, str]  # (peso, tono, texto)

NIVELES = {
    "IRON": "Hierro",
    "BRONZE": "Bronce",
    "SILVER": "Plata",
    "GOLD": "Oro",
    "PLATINUM": "Platino",
    "EMERALD": "Esmeralda",
    "DIAMOND": "Diamante",
    "MASTER": "Maestro",
    "GRANDMASTER": "Gran Maestro",
    "CHALLENGER": "Aspirante",
}
SIN_DIVISION = ("MASTER", "GRANDMASTER", "CHALLENGER")
ORDEN_POS = {p: i for i, p in enumerate(an.POSICIONES)}


class Sesion:
    def __init__(self, app: "App", juego: Json, yo: str, origen: str) -> None:
        self.app = app
        self.id = juego["gameId"]
        self.cola = juego.get("gameQueueConfigId", 0)
        self.mapa = juego.get("mapId", 0)
        self.inicio = juego.get("gameStartTime", 0)
        self.origen = origen  # 'propia' o 'manual'
        self.yo = yo
        self.modo = modo_de(self.cola, self.mapa)
        # En la Grieta, cinco contra cinco y con posiciones, el panel completo; en ARAM y el resto, lo básico de cada
        # jugador (su rango y su maestría con el campeón), sin pedir su historial.
        self.completo = self.modo in MODOS_GRIETA
        self.mi_rol = ""  # tu posición (o la del jugador buscado), ya repartidas las de todos
        self.motivo_rol = ""  # por qué es esa (analisis.MOTIVOS_ROL); solo en tu partida
        self.cancelada = False
        self.terminada = False
        self.total = 0
        self.hechas = 0
        self._lock = threading.RLock()
        self._sucio = True
        self._panel: Panel | None = None
        self._ts_panel = 0.0
        self.jugadores: list[Json] = []
        for p in juego.get("participants", []):
            nombre, _, tag = (p.get("riotId") or "").partition("#")
            # Con el perfil oculto Riot no da PUUID y pone el campeón como nombre.
            oculto = not p.get("puuid")
            self.jugadores.append(
                {
                    "puuid": p.get("puuid") or "",
                    "nombre": "Perfil oculto" if oculto or not nombre else nombre,
                    "tag": tag,
                    "equipo": p.get("teamId", 0),
                    "campeon": p.get("championId", 0),
                    "s1": p.get("spell1Id", 0),
                    "s2": p.get("spell2Id", 0),
                    "rol": "",
                    "liga": None,
                    "maestria": None,
                    "ids": None,
                    "cargadas": set(),
                    "lineas": set(),
                    "lineas_pedidas": set(),
                }
            )
        mio = next((j for j in self.jugadores if j["puuid"] == yo), None)
        self.mi_equipo = mio["equipo"] if mio else 100
        self.bans = [b.get("championId", 0) for b in juego.get("bannedChampions", []) if b.get("championId", 0) > 0]
        self._roles()

    # --- tareas ----------------------------------------------------------------------
    def _cancelada(self) -> bool:
        return self.cancelada

    def cancelar(self) -> None:
        self.cancelada = True

    def _poner(self, prioridad: int, fn: Callable[..., None], *args: Any) -> None:
        with self._lock:
            self.total += 1
        self.app.cola.poner(prioridad, self._ejecutar, fn, args)

    def _ejecutar(self, fn: Callable[..., None], args: tuple[Any, ...]) -> None:
        try:
            if not self.cancelada:
                fn(*args)
        finally:
            with self._lock:
                self.hechas += 1
                self._sucio = True

    def lanzar(self) -> None:
        for j in self.jugadores:
            if not j["puuid"]:
                continue
            if self.completo:
                self._poner(10, self._t_ids, j)
            self._poner(11, self._t_liga, j)
            self._poner(12, self._t_maestria, j)

    def _rival_clave(self, j: Json) -> str:
        """La posición de la que se piden más líneas de tiempo de este jugador: la de jungla para el jungla rival (su
        perfil y sus ganks) y la tuya para tu rival de línea, si no juegas jungla. '' para los demás."""
        if j["equipo"] == self.mi_equipo or not j["rol"]:
            return ""
        return str(j["rol"]) if j["rol"] in ("JUNGLE", self.mi_rol) else ""

    def _t_liga(self, j: Json) -> None:
        cache = self.app.cache
        clave = f"liga:{j['puuid']}"
        ligas = cache.kv_get(clave, max_edad=1800)
        if ligas is None:
            ligas = self.app.cliente.ligas(j["puuid"], cancelada=self._cancelada)
            if self.cancelada:
                return
            ligas = ligas or []
            cache.kv_set(clave, ligas)
        j["liga"] = ligas

    def _t_maestria(self, j: Json) -> None:
        """Una sola consulta trae la maestría de toda la cuenta: la del campeón de hoy, sus mains y el total."""
        cache = self.app.cache
        clave = f"maestrias:{j['puuid']}"
        todas = cache.kv_get(clave, max_edad=6 * 3600)
        if todas is None:
            lista = self.app.cliente.maestrias(j["puuid"], cancelada=self._cancelada)
            if self.cancelada:
                return
            todas = {str(m["championId"]): [m.get("championPoints", 0), m.get("lastPlayTime", 0)] for m in lista or []}
            cache.kv_set(clave, todas)
        puntos, ultimo = todas.get(str(j["campeon"]), [0, 0])
        mains = sorted(todas.items(), key=lambda x: x[1][0], reverse=True)[:3]
        j["maestria"] = {
            "championPoints": puntos,
            "lastPlayTime": ultimo,
            "total": sum(v[0] for v in todas.values()),
            "mains": [{"nombre": self.app.datos.nombre(int(c)), "puntos": v[0]} for c, v in mains],
        }

    def _t_ids(self, j: Json) -> None:
        cache = self.app.cache
        n = self.app.cfg["partidas_por_jugador"]
        cola = self.cola if self.cola in LIGA_COLA else None
        clave = f"ids:{j['puuid']}:{cola or 0}:{n}"
        ids = cache.kv_get(clave, max_edad=300)
        if ids is None:
            ids = self.app.cliente.ids_partidas(j["puuid"], cola=cola, n=n, cancelada=self._cancelada)
            if self.cancelada:
                return
            cache.kv_set(clave, ids)
        with self._lock:
            j["ids"] = ids
        importa = bool(self._rival_clave(j))  # el jungla rival o tu rival de línea: sus partidas, antes
        for k, id_ in enumerate(ids):
            if k < 5:
                prioridad = (14 if importa else 20) + k
            elif k < 10:
                prioridad = (25 if importa else 40) + k
            else:
                prioridad = 60 + k
            self._poner(prioridad, self._t_partida, j, id_)

    def _t_partida(self, j: Json, id_: str) -> None:
        red = self.app.traer_partida(id_, self._cancelada)
        if not red:
            return
        with self._lock:
            j["cargadas"].add(id_)
            self._roles()
        self._quizas_linea(j, red)

    def _quizas_linea(self, j: Json, red: Partida) -> None:
        """Decide si merece la pena pedir la línea de tiempo de esta partida (es la consulta cara)."""
        if j["puuid"] == self.yo or red["remake"] or red["cola"] not in COLAS_GRIETA:
            return
        en = an.jugador_en(red, j["puuid"])
        if not en:
            return
        cfg = self.app.cfg
        with self._lock:
            pedidas = j["lineas_pedidas"]
            if red["id"] in pedidas:
                return
            clave = self._rival_clave(j)
            if clave:
                # Del jungla rival y de tu rival de línea, solo las de esa posición: son las que dicen cómo la juega.
                tope = cfg["lineas_jungla_rival"] if clave == "JUNGLE" else cfg.get("lineas_rival_linea", 6)
                if en["pos"] != clave or len(pedidas) >= tope:
                    return
                prioridad = (30 if clave == "JUNGLE" else 32) + len(pedidas)
            else:
                if len(pedidas) >= cfg["lineas_por_jugador"]:
                    return
                # Las dos primeras de cada jugador entran en la primera tanda de cuota:
                # sin ellas no hay muertes tempranas y la sección de líneas se queda coja.
                prioridad = (35 if len(pedidas) < 2 else 50) + len(pedidas)
            pedidas.add(red["id"])
        self._poner(prioridad, self._t_linea, j, red["id"])

    def _t_linea(self, j: Json, id_: str) -> None:
        if self.app.traer_linea(id_, self._cancelada):
            with self._lock:
                j["lineas"].add(id_)

    # --- roles -------------------------------------------------------------------------
    def _muestra(self, j: Json) -> list[Partida]:
        cache = self.app.cache
        return [m for m in (cache.partida(i) for i in (j["ids"] or []) if i in j["cargadas"]) if m]

    def _roles(self) -> None:
        """Reparte las posiciones de cada equipo (solo en la Grieta). En tu partida la tuya es la de hoy
        (App.rol_de_hoy) y las demás se reparten alrededor; en la de otro, todas por campeón, hechizos e historial."""
        if not self.completo:
            return
        with self._lock:
            for equipo in (100, 200):
                grupo = [j for j in self.jugadores if j["equipo"] == equipo]
                historiales: dict[str, Counter[str]] = {}
                for j in grupo:
                    posiciones: Counter[str] = Counter()
                    for m in an.validas(self._muestra(j)):
                        en = an.jugador_en(m, j["puuid"])
                        if en and en["pos"]:
                            posiciones[en["pos"]] += 1
                    if posiciones:
                        historiales[j["puuid"]] = posiciones
                roles = an.asignar_roles(grupo, self.app.datos.roles, historiales)
                yo = next((i for i, j in enumerate(grupo) if j["puuid"] == self.yo), None)
                if yo is not None and self.origen == "propia" and roles[yo]:
                    con_smite = an.SMITE in (grupo[yo]["s1"], grupo[yo]["s2"])
                    rol, self.motivo_rol = self.app.rol_de_hoy(con_smite, roles[yo])
                    if rol != roles[yo]:
                        roles = an.asignar_roles(grupo, self.app.datos.roles, historiales, fijos={yo: rol})
                for j, rol in zip(grupo, roles, strict=True):
                    j["rol"] = rol
            mio = next((j for j in self.jugadores if j["puuid"] == self.yo), None)
            self.mi_rol = mio["rol"] if mio else ""

    def cambiar_rol(self) -> None:
        """Has elegido otra posición para esta partida: se reparten otra vez y se piden las líneas de tiempo de tu nuevo
        rival de línea (de las partidas suyas que ya están bajadas)."""
        self._roles()
        with self._lock:
            self._panel = None  # se vuelve a montar en cuanto se pida, sin esperar al segundo de rigor
            claves = [j for j in self.jugadores if self._rival_clave(j)]
        for j in claves:
            for m in self._muestra(j):
                self._quizas_linea(j, m)

    # --- panel -------------------------------------------------------------------------
    def invalidar_panel(self) -> None:
        """Ha cambiado algo de fuera que sale en el panel (notas, ajustes): se vuelve a montar al pedirlo."""
        self._sucio = True

    def panel(self) -> Panel:
        with self._lock:
            ahora = time.time()
            if self._panel is None or (self._sucio and ahora - self._ts_panel >= 1.0):
                self._sucio = False
                self._ts_panel = ahora
                self._panel = self._montar()
            self._panel["progreso"] = {"hechas": self.hechas, "total": self.total}
            self._panel["terminada"] = self.terminada
            return self._panel

    def _liga_ui(self, ligas: list[Json] | None) -> dict[str, LigaUI | None] | None:
        """Rango de solo/dúo siempre (es el que dice el nivel real); en flexible, además el de flex."""
        if ligas is None:
            return None

        def una(tipo: str) -> LigaUI | None:
            e = next((x for x in ligas if x.get("queueType") == tipo), None)
            if not e:
                return None
            tier = e.get("tier", "")
            txt = NIVELES.get(tier, tier.capitalize())
            if tier not in SIN_DIVISION:
                txt += f" {e.get('rank', '')}"
            return {
                "nivel": tier.lower(),
                "rank": e.get("rank", ""),
                "txt": txt,
                "lp": e.get("leaguePoints", 0),
                "v": e.get("wins", 0),
                "d": e.get("losses", 0),
            }

        return {"solo": una(LIGA_COLA[SOLO_DUO]), "flex": una(LIGA_COLA[FLEXIBLE]) if self.cola == FLEXIBLE else None}

    def _montar(self) -> Panel:
        app = self.app
        datos = app.datos
        ahora_ms = int(time.time() * 1000)
        muestras = {j["puuid"]: self._muestra(j) for j in self.jugadores if j["puuid"]}
        lineas = self._lineas_cargadas()
        grupos, letra = self._grupos(muestras)
        filas, equipos = self._jugadores(muestras, lineas, grupos, letra, ahora_ms)
        yo = next((j for j in self.jugadores if j["puuid"] == self.yo), None)
        comun: Panel = {
            "id": self.id,
            "cola": COLAS.get(self.cola, MODOS[self.modo] if self.modo != "otros" else f"Cola {self.cola}"),
            "modo": self.modo,
            "completo": self.completo,
            "rol": {
                "actual": self.mi_rol,
                "motivo": an.MOTIVOS_ROL.get(self.motivo_rol, ""),
                # Desde el panel solo se cambia la tuya, y solo en la Grieta (fuera no hay posiciones).
                "elegible": self.origen == "propia" and self.completo,
            },
            "yo": {"campeon": datos.nombre(yo["campeon"]), "splash": datos.splash(yo["campeon"])} if yo else None,
            "grieta": self.mapa == GRIETA,
            "inicio": self.inicio,
            "origen": self.origen,
            "equipos": equipos,
            "bans": [{"nombre": datos.nombre(b), "icono": datos.icono(b)} for b in self.bans],
            "recordatorios": app.cfg.get("recordatorios", []) if self.origen == "propia" else [],
            "notas": self._notas(),
        }
        if not self.completo:
            vacio: Panel = {"jungla": None, "rival_linea": None, "lineas": [], "gank": None, "historial": None, "plan": []}
            return {**comun, **vacio, "duelo": None, "avisos": self._avisos_basicos(filas)}
        por_pos = self._por_posicion(filas)
        jr = por_pos["rival"].get("JUNGLE")
        jungla, perfil = self._jungla_rival(jr, muestras, lineas)
        # Si no juegas jungla, tu rival directo es el de tu línea (de jungla, es el jungla rival de arriba).
        rl = por_pos["rival"].get(self.mi_rol) if self.mi_rol not in ("", "JUNGLE") else None
        rival_linea, perfil_linea = self._rival_de_linea(rl, muestras, lineas)
        lineas_juego = an.lineas_de_juego(por_pos["aliado"], por_pos["rival"])
        gank = _gank(perfil)
        historial = self._historial(muestras, por_pos, ahora_ms)
        avisos = self._avisos(filas, perfil, jr, historial, grupos, perfil_linea, rl)
        return {
            **comun,
            "duelo": self._duelo(yo, por_pos),
            "jungla": jungla,
            "rival_linea": rival_linea,
            "lineas": lineas_juego,
            "gank": gank,
            "historial": historial,
            "avisos": avisos,
            "plan": self._plan(lineas_juego, perfil, gank, perfil_linea, rl),
        }

    def _lineas_cargadas(self) -> dict[str, Linea]:
        """Las líneas de tiempo ya bajadas de las partidas de los diez: {id: línea}."""
        lineas: dict[str, Linea] = {}
        for j in self.jugadores:
            for id_ in j["lineas"]:
                linea = self.app.cache.linea(id_)
                if linea:
                    lineas[id_] = linea
        return lineas

    def _grupos(self, muestras: dict[str, list[Partida]]) -> tuple[dict[str, int], dict[tuple[int, int | None], str]]:
        """Grupos que vienen juntos, deducidos del historial público (como Porofessor, Blitz y compañía).

        Devuelve ({puuid: número de grupo}, {(equipo, grupo): letra}): la letra distingue dos grupos del mismo equipo.
        """
        grupos: dict[str, int] = {}
        for equipo in (100, 200):
            grupos.update(an.premades([j["puuid"] for j in self.jugadores if j["equipo"] == equipo and j["puuid"]], muestras))
        letra: dict[tuple[int, int | None], str] = {}
        for j in self.jugadores:
            g = grupos.get(j["puuid"])
            if g and (j["equipo"], g) not in letra:
                letra[(j["equipo"], g)] = "ABCDE"[sum(1 for e, _ in letra if e == j["equipo"])]
        return grupos, letra

    def _jugadores(
        self,
        muestras: dict[str, list[Partida]],
        lineas: dict[str, Linea],
        grupos: dict[str, int],
        letra: dict[tuple[int, int | None], str],
        ahora_ms: int,
    ) -> tuple[Filas, dict[str, list[Json]]]:
        """(datos de trabajo de cada jugador para las secciones de abajo, los dos equipos tal y como salen en el panel)."""
        filas: Filas = {}  # puuid -> resumen, etiquetas... del jugador
        equipos: dict[str, list[Json]] = {"aliado": [], "rival": []}
        for j in self.jugadores:
            res = an.resumen_jugador(j["puuid"], muestras.get(j["puuid"], []), j["campeon"], lineas)
            grupo = letra.get((j["equipo"], grupos.get(j["puuid"])), "")
            etiquetas = self._etiquetas(j, res, grupo, ahora_ms)
            primera_vez = any(e["t"] in ("Primera vez", "Poco rodado") for e in etiquetas)
            lado = "aliado" if j["equipo"] == self.mi_equipo else "rival"
            filas[j["puuid"] or id(j)] = {"j": j, "res": res, "etiquetas": etiquetas, "primera_vez": primera_vez, "lado": lado}
            equipos[lado].append(self._fila_del_panel(j, res, etiquetas, grupo))
        for lista in equipos.values():
            lista.sort(key=lambda f: ORDEN_POS.get(f["rol"], 9))
        return filas, equipos

    def _etiquetas(self, j: Json, res: Json, grupo: str, ahora_ms: int) -> list[Etiqueta]:
        con_datos = res["n"] or (not self.completo and j["maestria"] is not None)
        etiquetas = an.etiquetas(res, j["rol"], j["maestria"], ahora_ms) if con_datos else []
        if grupo and j["puuid"] != self.yo:
            etiquetas.insert(
                0,
                {
                    "t": f"Premade {grupo}",
                    "tono": "neutro",
                    "d": "ha jugado en el mismo equipo que otro jugador de esta partida en 2 o más partidas recientes",
                },
            )
        return etiquetas

    def _fila_del_panel(self, j: Json, res: Json, etiquetas: list[Etiqueta], grupo: str) -> Json:
        datos = self.app.datos
        maestria = j["maestria"]
        return {
            "nombre": j["nombre"],
            "tag": j["tag"],
            "campeon": datos.nombre(j["campeon"]),
            "icono": datos.icono(j["campeon"]),
            "rol": j["rol"],
            "rol_txt": an.NOMBRE_POS.get(j["rol"], ""),
            "soy_yo": j["puuid"] == self.yo,
            "oculto": not j["puuid"],
            "liga": self._liga_ui(j["liga"]),
            "maestria": None if maestria is None else maestria.get("championPoints", 0),
            "mains": (maestria or {}).get("mains", []),
            "muestra": {"n": res["n"], "v": res["v"]},
            "camp": res["camp"],
            "kda": res["kda"],
            "racha": res["racha"],
            "etiquetas": etiquetas,
            "grupo": grupo,
            "cargando": bool(j["puuid"]) and self._cargando(j),
        }

    def _cargando(self, j: Json) -> bool:
        """Si aún faltan sus datos: en la Grieta, sus 5 primeras partidas; fuera, su rango y su maestría."""
        if not self.completo:
            return j["liga"] is None or j["maestria"] is None
        return j["ids"] is None or len(j["cargadas"]) < min(5, len(j["ids"]))

    def _por_posicion(self, filas: Filas) -> PorPosicion:
        """{'aliado'|'rival': {posición: jugador}} para comparar línea a línea."""
        por_pos: PorPosicion = {"aliado": {}, "rival": {}}
        for f in filas.values():
            j = f["j"]
            por_pos[f["lado"]][j["rol"]] = {
                "nombre": j["nombre"],
                "campeon": self.app.datos.nombre(j["campeon"]),
                "res": f["res"],
                "primera_vez": f["primera_vez"],
                "j": j,
            }
        return por_pos

    def _jungla_rival(
        self, jr: Json | None, muestras: dict[str, list[Partida]], lineas: dict[str, Linea]
    ) -> tuple[Json | None, Json | None]:
        """(lo que enseña el panel del jungla rival, su perfil), o (None, None) si no se sabe quién es."""
        if not (jr and jr["j"]["puuid"]):
            return None, None
        j = jr["j"]
        perfil = an.perfil_jungla(j["puuid"], muestras.get(j["puuid"], []), lineas, j["campeon"], j["equipo"])
        jungla = {
            "nombre": j["nombre"],
            "campeon": jr["campeon"],
            "icono": self.app.datos.icono(j["campeon"]),
            "n": perfil["n"],
            "n_campeon": perfil["n_campeon"],
            "n_lineas": perfil["n_lineas"],
            "tarjetas": perfil["tarjetas"],
            "mapa": perfil.get("mapa") or {},
            "cargando": j["ids"] is None or len(j["lineas"]) < len(j["lineas_pedidas"]),
        }
        return jungla, perfil

    def _rival_de_linea(
        self, rl: Json | None, muestras: dict[str, list[Partida]], lineas: dict[str, Linea]
    ) -> tuple[Json | None, Json | None]:
        """(lo que enseña el panel de tu rival de línea, su perfil), o (None, None) si juegas jungla o no se sabe quién
        es (perfil oculto)."""
        if not (rl and rl["j"]["puuid"]):
            return None, None
        j = rl["j"]
        perfil = an.perfil_linea(j["puuid"], muestras.get(j["puuid"], []), lineas, j["campeon"], j["rol"])
        caja = {
            "nombre": j["nombre"],
            "campeon": rl["campeon"],
            "icono": self.app.datos.icono(j["campeon"]),
            "rol": j["rol"],
            "n": perfil["n"],
            "n_campeon": perfil["n_campeon"],
            "n_lineas": perfil["n_lineas"],
            "tarjetas": perfil["tarjetas"],
            "al10": perfil["al10"],  # para comprobarlo en la revisión
            "cargando": j["ids"] is None or len(j["lineas"]) < len(j["lineas_pedidas"]),
        }
        return caja, perfil

    def _duelo(self, yo: Json | None, por_pos: PorPosicion) -> Json | None:
        """Tu duelo contra el rival de tu posición, según las partidas de Master+."""
        if not (yo and yo["rol"]):
            return None
        rival_directo = por_pos["rival"].get(yo["rol"])
        return self.app.duelo(yo["campeon"], yo["rol"], rival_directo["j"]["campeon"]) if rival_directo else None

    def _notas(self) -> list[Json]:
        """Tus notas de los campeones de la partida (solo en la tuya)."""
        if self.origen != "propia":
            return []
        rivales = {j["campeon"] for j in self.jugadores if j["equipo"] != self.mi_equipo}
        return self.app.notas_de([j["campeon"] for j in self.jugadores], rivales)

    def _historial(self, muestras: dict[str, list[Partida]], por_pos: PorPosicion, ahora_ms: int) -> Json | None:
        app = self.app
        yo = next((j for j in self.jugadores if j["puuid"] == self.yo), None)
        if not yo:
            return None
        if self.origen == "propia":
            mis_puuids = set(app.cuentas)
            # Solo/dúo y flexible son mundos distintos (otro nivel, otros campeones): no se mezclan.
            mias = app.mis_partidas(self.cola)
            alcance = "temporada"
        else:
            mis_puuids = {self.yo}
            mias = muestras.get(self.yo, [])
            alcance = "muestra"
        rivales = [
            {"campeon": d["j"]["campeon"], "pos": pos, "nombre_campeon": d["campeon"]} for pos, d in por_pos["rival"].items()
        ]
        presentes = {j["puuid"]: j["nombre"] for j in self.jugadores if j["puuid"] and j["puuid"] not in mis_puuids}
        h = an.mi_historial(mis_puuids, mias, yo["campeon"], rivales, presentes, ahora_ms, mi_pos=yo["rol"])
        h["alcance"] = alcance
        h["cola_txt"] = NOMBRE_LIGA.get(self.cola, "") if alcance == "temporada" else ""
        h["mi_campeon"] = app.datos.nombre(yo["campeon"])
        for fila in h["vs"]:
            fila["icono"] = app.datos.icono(fila["campeon"])
        return h

    def _avisos(
        self,
        filas: Filas,
        perfil: Json | None,
        jr: Json | None,
        historial: Json | None,
        grupos: dict[str, int],
        perfil_linea: Json | None = None,
        rl: Json | None = None,
    ) -> list[Aviso]:
        """Hechos destacados, con sus números. Nunca órdenes: Riot no permite apps que decidan por el jugador."""
        avisos: list[AvisoConPeso] = [
            *_aviso_de_tu_duelo(historial),
            *_avisos_del_jungla(perfil, jr),
            *_avisos_del_rival_de_linea(perfil_linea, rl),
            *self._avisos_de_jugadores(filas),
            *self._avisos_de_premades(filas, grupos),
        ]
        avisos.sort(key=lambda a: a[0], reverse=True)
        return [{"tono": tono, "texto": texto} for _, tono, texto in avisos[:7]]

    def _avisos_de_jugadores(self, filas: Filas) -> list[AvisoConPeso]:
        """Rivales que destacan (kills en solitario, racha con su campeón) y quién va con poco rodaje o fuera de rol."""
        avisos: list[AvisoConPeso] = []
        verdes: dict[str, list[str]] = {"aliado": [], "rival": []}
        for f in filas.values():
            j, res = f["j"], f["res"]
            campeon = self.app.datos.nombre(j["campeon"])
            rol = an.NOMBRE_POS.get(j["rol"], "")
            camp = res["camp"]
            if f["lado"] == "rival":
                if j["rol"] != "JUNGLE" and res["n"] >= 6 and res["solo"] >= an.UMBRAL_SOLO.get(j["rol"], 9):
                    avisos.append((5, "ojo", f"{campeon} ({rol}) saca {an.num(res['solo'])} kills en solitario por partida."))
                if camp["n"] >= 5 and camp["v"] / camp["n"] >= 0.7:
                    avisos.append(
                        (6, "ojo", f"{campeon} ({rol}) ha ganado {camp['v']} de sus últimas {camp['n']} con ese campeón.")
                    )
            if j["puuid"] != self.yo and (f["primera_vez"] or an.fuera_de_rol(res, j["rol"])):
                motivo = "poco rodaje" if f["primera_vez"] else "fuera de rol"
                verdes[f["lado"]].append(f"{campeon} ({rol}, {motivo})")
        # Una sola línea por equipo: en partidas con muchas cuentas secundarias salen varios a la vez.
        if verdes["rival"]:
            avisos.append((5, "neutro", "Rivales con poco rodaje o fuera de rol: " + ", ".join(verdes["rival"]) + "."))
        if verdes["aliado"]:
            avisos.append((4, "neutro", "Aliados con poco rodaje o fuera de rol: " + ", ".join(verdes["aliado"]) + "."))
        return avisos

    def _avisos_basicos(self, filas: Filas) -> list[Aviso]:
        """Fuera de la Grieta, lo que dice la maestría: quién domina su campeón y quién casi no lo ha jugado."""
        por_etiqueta: dict[tuple[str, str], list[str]] = {}
        for f in filas.values():
            j = f["j"]
            if j["puuid"] == self.yo:
                continue
            nombres = {e["t"] for e in f["etiquetas"]}
            campeon = self.app.datos.nombre(j["campeon"])
            if "Main" in nombres:
                por_etiqueta.setdefault((f["lado"], "mucha"), []).append(campeon)
            if nombres & {"Primera vez", "Poco rodado"}:
                por_etiqueta.setdefault((f["lado"], "poca"), []).append(campeon)
        textos = (
            (("rival", "mucha"), "ojo", "Rivales con mucha maestría en su campeón"),
            (("rival", "poca"), "bien", "Rivales que casi no han jugado su campeón"),
            (("aliado", "mucha"), "bien", "Aliados con mucha maestría en su campeón"),
            (("aliado", "poca"), "neutro", "Aliados que casi no han jugado su campeón"),
        )
        return [
            {"tono": tono, "texto": f"{texto}: {', '.join(por_etiqueta[clave])}."}
            for clave, tono, texto in textos
            if por_etiqueta.get(clave)
        ]

    def _avisos_de_premades(self, filas: Filas, grupos: dict[str, int]) -> list[AvisoConPeso]:
        por_grupo: dict[int, list[str]] = {}
        for f in filas.values():
            if f["lado"] == "rival" and f["j"]["puuid"] in grupos:
                por_grupo.setdefault(grupos[f["j"]["puuid"]], []).append(self.app.datos.nombre(f["j"]["campeon"]))
        return [(3, "neutro", f"Premade rival: {' + '.join(nombres)}.") for nombres in por_grupo.values()]

    def _plan(
        self,
        lineas_juego: list[Json],
        perfil: Json | None,
        gank: Json | None,
        perfil_linea: Json | None = None,
        rl: Json | None = None,
    ) -> list[str]:
        """Dos o tres frases para leer en la pantalla de carga. De jungla: qué línea rival falla más, dónde sufre tu
        equipo y por dónde empieza y adónde va el jungla rival. De línea: cómo llega tu rival al 10 y adónde van su
        primer gank y su jungla."""
        if self.mi_rol not in ("", "JUNGLE"):
            rival = rl["campeon"] if rl else None
            return plan_de_linea(self.mi_rol, rival, (perfil_linea or {}).get("al10"), gank, (perfil or {}).get("inicio"))
        plan: list[str] = []
        if lineas_juego:
            mejor = lineas_juego[0]
            if mejor["veredicto"] == "Aquí se equivocan" and mejor["rival"]:
                plan.append(f"Más errores esperados en {mejor['linea']}: {mejor['rival'][0]}.")
            peor = min(lineas_juego, key=lambda x: x["diferencia"])
            if peor["tono"] == "ojo":
                plan.append(f"{peor['linea'].capitalize()} es donde sufre tu equipo.")
        inicio = (perfil or {}).get("inicio")
        if inicio and inicio["marcado"]:
            lado = "arriba" if inicio["lado"] == "sup" else "abajo"
            plan.append(f"Su jungla suele empezar en {inicio['buff']}: hoy, {lado}.")
        if gank:
            plan.append(f"Su primer gank va a {gank['linea']} en {gank['veces']} de {gank['n']}.")
        return plan[:3]


def plan_de_linea(mi_rol: str, rival: str | None, al10: Json | None, gank: Json | None, inicio: Json | None) -> list[str]:
    """El plan cuando no juegas jungla: cómo llega tu rival (su campeón) al 10 y adónde van el primer gank y el inicio
    del jungla rival. También lo usa la demo."""
    plan: list[str] = []
    if rival and al10 and al10["n"] >= 3 and abs(al10["oro"]) >= 300:
        plan.append(
            f"{rival} suele llegar al 10 con {an.con_signo(al10['oro'])} de oro frente a su rival ({al10['n']} partidas)."
        )
    if gank:
        a_donde = "a tu línea" if gank["linea"] == an.LINEA_DE.get(mi_rol) else f"a {gank['linea']}"
        plan.append(f"Su primer gank va {a_donde} en {gank['veces']} de {gank['n']}.")
    if inicio and inicio["marcado"]:
        lado = "arriba" if inicio["lado"] == "sup" else "abajo"
        plan.append(f"Su jungla suele empezar en {inicio['buff']}: hoy, {lado}.")
    return plan[:3]


def _gank(perfil: Json | None) -> Json | None:
    """Si su primer gank va casi siempre a la misma línea (4 o más partidas, la mitad o más): {línea, veces, n}."""
    if not (perfil and perfil["ganks"]):
        return None
    total = sum(perfil["ganks"].values())
    linea, veces = max(perfil["ganks"].items(), key=lambda x: x[1])
    if total >= 4 and veces / total >= 0.5:
        return {"linea": linea, "veces": veces, "n": total}
    return None


def _aviso_de_tu_duelo(historial: Json | None) -> list[AvisoConPeso]:
    """Cómo te va contra el campeón de tu rival de posición: con tu campeón de hoy o, si no, con cualquiera."""
    if not historial:
        return []
    vj = historial.get("vs_directo")
    if vj and vj["n_mio"] >= 2:
        d = vj["n_mio"] - vj["v_mio"]
        tono = "ojo" if vj["v_mio"] < d else ("bien" if vj["v_mio"] > d else "neutro")
        texto = f"{historial['mi_campeon']} contra {vj['nombre']} en {vj['pos']}: {vj['v_mio']}V {d}D."
        return [(9 if tono == "ojo" else 4, tono, texto)]
    if vj and vj["n"] >= 3:
        d = vj["n"] - vj["v"]
        tono = "ojo" if vj["v"] < d else ("bien" if vj["v"] > d else "neutro")
        return [(6 if tono == "ojo" else 3, tono, f"Contra {vj['nombre']} en {vj['pos']} llevas {vj['v']}V {d}D.")]
    return []


def _avisos_del_rival_de_linea(perfil: Json | None, rl: Json | None) -> list[AvisoConPeso]:
    """Si tu rival de línea gana casi siempre cuando va por delante al 10."""
    if not (perfil and perfil["snowball"] and rl):
        return []
    gana, veces = perfil["snowball"]["delante"]
    if veces >= 3 and gana / veces >= 0.75:
        return [
            (
                8,
                "ojo",
                f"{rl['campeon']} ({an.NOMBRE_POS.get(rl['j']['rol'], '')}) gana {gana} de {veces} cuando va por delante al 10.",
            )
        ]
    return []


def _avisos_del_jungla(perfil: Json | None, jr: Json | None) -> list[AvisoConPeso]:
    """Si el jungla rival gana casi siempre cuando va por delante o saca muchas kills en solitario."""
    if not (perfil and perfil["snowball"] and jr):
        return []
    avisos: list[AvisoConPeso] = []
    s = perfil["snowball"]
    gana, veces = s["delante"]
    if veces >= 3 and gana / veces >= 0.75:
        avisos.append((8, "ojo", f"{jr['campeon']} gana {gana} de {veces} cuando va por delante al minuto 10."))
    if s["solo"] >= an.UMBRAL_SOLO["JUNGLE"] and perfil["n"] >= 4:
        avisos.append((7, "ojo", f"{jr['campeon']} saca {an.num(s['solo'])} kills en solitario por partida."))
    return avisos
