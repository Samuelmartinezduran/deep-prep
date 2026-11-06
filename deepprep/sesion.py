"""Una partida en vivo: pide los datos de los diez jugadores y monta el panel."""

import threading
import time
from collections import Counter

from . import analisis as an
from .constantes import COLAS, COLAS_GRIETA, FLEXIBLE, GRIETA, LIGA_COLA, NOMBRE_LIGA, SOLO_DUO

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
    def __init__(self, app, juego, yo, origen):
        self.app = app
        self.id = juego["gameId"]
        self.cola = juego.get("gameQueueConfigId", 0)
        self.mapa = juego.get("mapId", 0)
        self.inicio = juego.get("gameStartTime", 0)
        self.origen = origen  # 'propia' o 'manual'
        self.yo = yo
        self.cancelada = False
        self.terminada = False
        self.total = 0
        self.hechas = 0
        self._lock = threading.RLock()
        self._sucio = True
        self._panel = None
        self._ts_panel = 0.0
        self.jugadores = []
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
    def _cancelada(self):
        return self.cancelada

    def cancelar(self):
        self.cancelada = True

    def _poner(self, prioridad, fn, *args):
        with self._lock:
            self.total += 1
        self.app.cola.poner(prioridad, self._ejecutar, fn, args)

    def _ejecutar(self, fn, args):
        try:
            if not self.cancelada:
                fn(*args)
        finally:
            with self._lock:
                self.hechas += 1
                self._sucio = True

    def lanzar(self):
        for j in self.jugadores:
            if not j["puuid"]:
                continue
            self._poner(10, self._t_ids, j)
            self._poner(11, self._t_liga, j)
            self._poner(12, self._t_maestria, j)

    def _es_jungla_rival(self, j):
        return j["equipo"] != self.mi_equipo and j["rol"] == "JUNGLE"

    def _t_liga(self, j):
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

    def _t_maestria(self, j):
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

    def _t_ids(self, j):
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
        jungla_rival = self._es_jungla_rival(j)
        for k, id_ in enumerate(ids):
            if k < 5:
                prioridad = (14 if jungla_rival else 20) + k
            elif k < 10:
                prioridad = (25 if jungla_rival else 40) + k
            else:
                prioridad = 60 + k
            self._poner(prioridad, self._t_partida, j, id_)

    def _t_partida(self, j, id_):
        red = self.app.traer_partida(id_, self._cancelada)
        if not red:
            return
        with self._lock:
            j["cargadas"].add(id_)
            self._roles()
        self._quizas_linea(j, red)

    def _quizas_linea(self, j, red):
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
            if self._es_jungla_rival(j):
                if en["pos"] != "JUNGLE" or len(pedidas) >= cfg["lineas_jungla_rival"]:
                    return
                prioridad = 30 + len(pedidas)
            else:
                if len(pedidas) >= cfg["lineas_por_jugador"]:
                    return
                # Las dos primeras de cada jugador entran en la primera tanda de cuota:
                # sin ellas no hay muertes tempranas y la sección de líneas se queda coja.
                prioridad = (35 if len(pedidas) < 2 else 50) + len(pedidas)
            pedidas.add(red["id"])
        self._poner(prioridad, self._t_linea, j, red["id"])

    def _t_linea(self, j, id_):
        if self.app.traer_linea(id_, self._cancelada):
            with self._lock:
                j["lineas"].add(id_)

    # --- roles -------------------------------------------------------------------------
    def _muestra(self, j):
        cache = self.app.cache
        return [m for m in (cache.partida(i) for i in (j["ids"] or []) if i in j["cargadas"]) if m]

    def _roles(self):
        with self._lock:
            for equipo in (100, 200):
                grupo = [j for j in self.jugadores if j["equipo"] == equipo]
                historiales = {}
                for j in grupo:
                    posiciones = Counter()
                    for m in an.validas(self._muestra(j)):
                        en = an.jugador_en(m, j["puuid"])
                        if en and en["pos"]:
                            posiciones[en["pos"]] += 1
                    if posiciones:
                        historiales[j["puuid"]] = posiciones
                for j, rol in zip(grupo, an.asignar_roles(grupo, self.app.datos.roles, historiales), strict=True):
                    j["rol"] = rol

    # --- panel -------------------------------------------------------------------------
    def panel(self):
        with self._lock:
            ahora = time.time()
            if self._panel is None or (self._sucio and ahora - self._ts_panel >= 1.0):
                self._sucio = False
                self._ts_panel = ahora
                self._panel = self._montar()
            self._panel["progreso"] = {"hechas": self.hechas, "total": self.total}
            self._panel["terminada"] = self.terminada
            return self._panel

    def _liga_ui(self, ligas):
        """Rango de solo/dúo siempre (es el que dice el nivel real); en flexible, además el de flex."""
        if ligas is None:
            return None

        def una(tipo):
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

    def _montar(self):
        app = self.app
        datos = app.datos
        ahora_ms = int(time.time() * 1000)
        muestras = {j["puuid"]: self._muestra(j) for j in self.jugadores if j["puuid"]}
        lineas = self._lineas_cargadas()
        grupos, letra = self._grupos(muestras)
        filas, equipos = self._jugadores(muestras, lineas, grupos, letra, ahora_ms)
        por_pos = self._por_posicion(filas)
        jr = por_pos["rival"].get("JUNGLE")
        jungla, perfil = self._jungla_rival(jr, muestras, lineas)
        lineas_juego = an.lineas_de_juego(por_pos["aliado"], por_pos["rival"])
        gank = _gank(perfil)
        historial = self._historial(muestras, por_pos, ahora_ms)
        avisos = self._avisos(filas, perfil, jr, historial, grupos)
        yo = next((j for j in self.jugadores if j["puuid"] == self.yo), None)
        return {
            "duelo": self._duelo(yo, por_pos),
            "id": self.id,
            "cola": COLAS.get(self.cola, f"Cola {self.cola}"),
            "yo": {"campeon": datos.nombre(yo["campeon"]), "splash": datos.splash(yo["campeon"])} if yo else None,
            "grieta": self.mapa == GRIETA,
            "inicio": self.inicio,
            "origen": self.origen,
            "equipos": equipos,
            "jungla": jungla,
            "lineas": lineas_juego,
            "gank": gank,
            "historial": historial,
            "avisos": avisos,
            "plan": self._plan(lineas_juego, perfil, gank),
            "bans": [{"nombre": datos.nombre(b), "icono": datos.icono(b)} for b in self.bans],
            "recordatorios": app.cfg.get("recordatorios", []) if self.origen == "propia" else [],
            "notas": self._notas(),
        }

    def _lineas_cargadas(self):
        """Las líneas de tiempo ya bajadas de las partidas de los diez: {id: línea}."""
        lineas = {}
        for j in self.jugadores:
            for id_ in j["lineas"]:
                linea = self.app.cache.linea(id_)
                if linea:
                    lineas[id_] = linea
        return lineas

    def _grupos(self, muestras):
        """Grupos que vienen juntos, deducidos del historial público (como Porofessor, Blitz y compañía).

        Devuelve ({puuid: número de grupo}, {(equipo, grupo): letra}): la letra distingue dos grupos del mismo equipo.
        """
        grupos = {}
        for equipo in (100, 200):
            grupos.update(an.premades([j["puuid"] for j in self.jugadores if j["equipo"] == equipo and j["puuid"]], muestras))
        letra = {}
        for j in self.jugadores:
            g = grupos.get(j["puuid"])
            if g and (j["equipo"], g) not in letra:
                letra[(j["equipo"], g)] = "ABCDE"[sum(1 for e, _ in letra if e == j["equipo"])]
        return grupos, letra

    def _jugadores(self, muestras, lineas, grupos, letra, ahora_ms):
        """(datos de trabajo de cada jugador para las secciones de abajo, los dos equipos tal y como salen en el panel)."""
        filas = {}  # puuid -> resumen, etiquetas... del jugador
        equipos = {"aliado": [], "rival": []}
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

    def _etiquetas(self, j, res, grupo, ahora_ms):
        etiquetas = an.etiquetas(res, j["rol"], j["maestria"], ahora_ms) if res["n"] else []
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

    def _fila_del_panel(self, j, res, etiquetas, grupo):
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
            "cargando": bool(j["puuid"]) and (j["ids"] is None or len(j["cargadas"]) < min(5, len(j["ids"]))),
        }

    def _por_posicion(self, filas):
        """{'aliado'|'rival': {posición: jugador}} para comparar línea a línea."""
        por_pos = {"aliado": {}, "rival": {}}
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

    def _jungla_rival(self, jr, muestras, lineas):
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

    def _duelo(self, yo, por_pos):
        """Tu duelo contra el rival de tu posición, según las partidas de Master+."""
        rival_directo = por_pos["rival"].get(yo["rol"]) if yo and yo["rol"] else None
        return self.app.duelo(yo["campeon"], yo["rol"], rival_directo["j"]["campeon"]) if rival_directo else None

    def _notas(self):
        """Tus notas de los campeones de la partida (solo en la tuya)."""
        if self.origen != "propia":
            return []
        rivales = {j["campeon"] for j in self.jugadores if j["equipo"] != self.mi_equipo}
        return self.app.notas_de([j["campeon"] for j in self.jugadores], rivales)

    def _historial(self, muestras, por_pos, ahora_ms):
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

    def _avisos(self, filas, perfil, jr, historial, grupos):
        """Hechos destacados, con sus números. Nunca órdenes: Riot no permite apps que decidan por el jugador."""
        avisos = [  # (peso, tono, texto)
            *_aviso_de_tu_duelo(historial),
            *_avisos_del_jungla(perfil, jr),
            *self._avisos_de_jugadores(filas),
            *self._avisos_de_premades(filas, grupos),
        ]
        avisos.sort(key=lambda a: a[0], reverse=True)
        return [{"tono": tono, "texto": texto} for _, tono, texto in avisos[:7]]

    def _avisos_de_jugadores(self, filas):
        """Rivales que destacan (kills en solitario, racha con su campeón) y quién va con poco rodaje o fuera de rol."""
        avisos = []
        verdes = {"aliado": [], "rival": []}
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

    def _avisos_de_premades(self, filas, grupos):
        por_grupo = {}
        for f in filas.values():
            if f["lado"] == "rival" and f["j"]["puuid"] in grupos:
                por_grupo.setdefault(grupos[f["j"]["puuid"]], []).append(self.app.datos.nombre(f["j"]["campeon"]))
        return [(3, "neutro", f"Premade rival: {' + '.join(nombres)}.") for nombres in por_grupo.values()]

    def _plan(self, lineas_juego, perfil, gank):
        """Dos o tres frases para leer en la pantalla de carga."""
        plan = []
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


def _gank(perfil):
    """Si su primer gank va casi siempre a la misma línea (4 o más partidas, la mitad o más): {línea, veces, n}."""
    if not (perfil and perfil["ganks"]):
        return None
    total = sum(perfil["ganks"].values())
    linea, veces = max(perfil["ganks"].items(), key=lambda x: x[1])
    if total >= 4 and veces / total >= 0.5:
        return {"linea": linea, "veces": veces, "n": total}
    return None


def _aviso_de_tu_duelo(historial):
    """Cómo te va contra el campeón de tu rival de posición: con tu campeón de hoy o, si no, con cualquiera."""
    vj = (historial or {}).get("vs_directo")
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


def _avisos_del_jungla(perfil, jr):
    """Si el jungla rival gana casi siempre cuando va por delante o saca muchas kills en solitario."""
    if not (perfil and perfil["snowball"] and jr):
        return []
    avisos = []
    s = perfil["snowball"]
    gana, veces = s["delante"]
    if veces >= 3 and gana / veces >= 0.75:
        avisos.append((8, "ojo", f"{jr['campeon']} gana {gana} de {veces} cuando va por delante al minuto 10."))
    if s["solo"] >= an.UMBRAL_SOLO["JUNGLE"] and perfil["n"] >= 4:
        avisos.append((7, "ojo", f"{jr['campeon']} saca {an.num(s['solo'])} kills en solitario por partida."))
    return avisos
