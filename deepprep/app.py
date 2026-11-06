"""Núcleo: vigila el cliente del LoL, abre una sesión por partida y da el estado al panel."""

import datetime
import json
import os
import threading
import time
import traceback
from pathlib import Path

from . import actualizador, clips, config, inicio_windows, lcu
from . import analisis as an
from . import duelos as du
from . import recolector as rec
from . import revision as rv
from .cache import Cache
from .ddragon import Datos
from .grabacion import GRIETA, Grabador, buscar_ffmpeg, inicio_de_series
from .overlay import MODO_SIN_BORDES, modo_ventana, parsear_atajo
from .riot import ClaveInvalida, Cliente, ErrorRiot
from .sesion import LIGA_COLA, NOMBRE_LIGA, Sesion
from .trabajo import Cola

FASES = {
    "None": "Cliente abierto",
    "Lobby": "En sala",
    "Matchmaking": "En cola",
    "ReadyCheck": "Partida encontrada",
    "ChampSelect": "Selección de campeón",
    "GameStart": "Empezando partida",
    "InProgress": "En partida",
    "Reconnect": "Reconectando",
    "WaitingForStats": "Fin de partida",
    "PreEndOfGame": "Fin de partida",
    "EndOfGame": "Fin de partida",
}
EN_JUEGO = ("GameStart", "InProgress", "Reconnect")


def _desfase(carpeta, inicio_ms):
    """Por cada serie de la grabación, segundos grabados antes del 0:00 de la partida: {serie: s}, o None.

    La grabación empieza en la pantalla de carga; si ffmpeg se relanza a media partida (p. ej. al cambiar la
    resolución), esa serie empieza ya jugando y su desfase es negativo.
    """
    if not carpeta or not inicio_ms:
        return None
    series = inicio_de_series(carpeta)
    if not series:
        return None
    return {n: round(inicio_ms / 1000 - t) for n, t in series.items()}


# Fases en las que la partida está al caer: el historial propio deja de descargarse.
PARTIDA_CERCA = ("Matchmaking", "ReadyCheck", "ChampSelect", "GameStart")


class App:
    def __init__(self, cfg=None, cache=None, datos=None, cliente=None, cliente_lol=None, grabador=None, duelos=None):
        # Las piezas se pueden pasar ya hechas para probar la app sin red ni cliente.
        # Solo se escribe config.json si la configuración salió de él (las pruebas no lo tocan).
        self._guardar_cfg = config.guardar if cfg is None else (lambda c: None)
        # El acceso directo de arranque con Windows solo se toca con la configuración de verdad.
        self._arranque_windows = inicio_windows.poner if cfg is None else (lambda encendido: "")
        self.cfg = cfg or config.cargar()
        # grabador=False: sin grabación aunque la configuración la pida (pruebas y simulaciones).
        if grabador is None and self.cfg.get("grabar"):
            grabador = Grabador(self.cfg)
        self.grabador = grabador or None
        self.cache = cache or Cache(config.RUTA_CACHE)
        self.datos = datos or Datos(self.cache)
        self.cliente = cliente or Cliente(self.cfg, config.leer_clave)
        self.cola = Cola(al_fallar=self._fallo_tarea)
        self.lcu = cliente_lol or lcu.Cliente(self.cfg["ruta_lol"])
        # Duelos de Master+ (lo llena el recolector). Las pruebas usan una base en memoria.
        self.duelos = duelos or (rec.BaseDuelos() if cfg is None else rec.BaseDuelos(":memory:"))
        self.recolector = None
        self.actualizador = actualizador.Actualizador(self)
        self.revisando = 0  # revisiones esperando a que Riot publique la partida (no actualizar mientras)
        self._duelos_cache = {}
        self._pool = (0.0, [])
        self._resumen_duelos = (0.0, None)
        self.inicio_temporada_ms = int(datetime.datetime.fromisoformat(self.cfg["inicio_temporada"]).timestamp() * 1000)
        self.cuentas = {}  # puuid -> "Nombre#TAG" de las cuentas propias
        self.cuenta_activa = None  # puuid de la cuenta abierta en el cliente
        self.sesion = None
        self.fase = None  # None = cliente cerrado
        # 'previa' (fuera de partida o en selección), 'carga' (pantalla de carga) o 'juego' (ya se juega).
        # En 'juego' el panel solo enseña datos: Riot no permite sacar conclusiones durante la partida.
        self.modo = "previa"
        self.reloj = None  # segundos de partida según el propio juego
        self.seleccion = None
        self.error_clave = ""
        self.sync = {"hechas": 0, "total": 0}
        self.ultima_consulta = time.time()  # última vez que el panel pidió el estado
        self.al_mostrar = None  # lo pone la ventana principal: otra copia arrancada pide enseñarla
        self.al_salir = None  # lo ponen las ventanas: cierra la app del todo
        self.ventana_visible = None  # lo ponen las ventanas: ¿está la principal a la vista?
        self._ventana_juego = (0.0, None)  # (cuándo se leyó, WindowMode del juego)
        self.ultima_revision = None  # id de la última revisión post-partida terminada
        self._lock = threading.RLock()
        self._en_curso = {}
        self._ultimo_sondeo = 0.0
        self._ultima_prueba_clave = 0.0
        self._fijada = False  # el usuario ha buscado otra partida a mano y no hay que pisársela
        self._ultimo_juego = None
        self._sel_clave = None
        self._mias = (None, [])
        self._plataforma_vista = False  # región del cliente ya mirada en esta sesión del cliente
        self._arranco = False  # arrancar() ya se llamó (las pruebas usan la app sin arrancarla)

    # --- arranque ---------------------------------------------------------------------
    def arrancar(self):
        self._arranco = True
        try:
            self._comprobar_clave()
        except ClaveInvalida as e:
            self.error_clave = str(e)
        except ErrorRiot as e:
            print(f"No se pudo comprobar la clave: {e}")
        threading.Thread(target=self._bucle, args=(self._paso, 2.5), name="vigia", daemon=True).start()
        threading.Thread(target=self._bucle, args=(self._fondo, 20), name="fondo", daemon=True).start()
        # Con cuentas ya conocidas la región también lo es; si no (app recién instalada), el recolector
        # espera a que se abra el cliente y diga de qué región es.
        if self.cfg["cuentas"]:
            self._arrancar_recolector()
        self.actualizador.arrancar()
        if config.CONGELADA and self.cfg.get("siempre_en_marcha") and not inicio_windows.activo():
            inicio_windows.poner(True)

    def _arrancar_recolector(self):
        if self.recolector or not self.cfg.get("recolectar", True):
            return
        # Tu región va con el cliente del panel (y su cuota); las demás, cada una con la suya.
        fuera = [(p, r) for p, r in rec.TODAS if r != self.cfg["region"]]
        self.recolector = rec.Recolector(
            self.duelos,
            config.leer_clave,
            self.datos.legendarios,
            pool=self.pool,
            mis_partidas=self.mis_partidas,
            mis_puuids=lambda: set(self.cuentas),
            cliente_europa=self.cliente,
            puede_europa=self._europa_libre,
            referencias=self._referencias,
            regiones=fuera,
        )
        if not self.recolector.arrancar():
            self.recolector = None

    # --- duelos de Master+ ---------------------------------------------------------------------
    def _europa_libre(self):
        """EUW comparte cuota con el panel: el recolector solo la usa con el cliente quieto."""
        return (
            not self.error_clave
            and self.fase not in PARTIDA_CERCA + EN_JUEGO
            and not self._cargando()
            and self.sync["hechas"] >= self.sync["total"]
        )

    def pool(self):
        """Tus campeones por posición (de tus clasificatorias de la temporada); se recalcula cada 10 min."""
        if time.time() - self._pool[0] > 600:
            self._pool = (time.time(), rec.pool_de(self.mis_partidas(), set(self.cuentas)))
        return self._pool[1]

    def duelo(self, a, pos, b):
        """Tu campeón contra su rival directo: lo que dicen las partidas de Master+ y tus números al lado."""
        if not (a and b and pos):
            return None
        clave = (a, pos, b)
        hecho = self._duelos_cache.get(clave)
        if hecho and time.time() - hecho[0] < 120:
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
                "en_pool": (a, pos) in set(self.pool()),
            }
        )
        self._duelos_cache[clave] = (time.time(), res)
        return res

    def pool_contra(self, pos, rival, cola=None):
        """Tu pool de esa posición contra el campeón rival (selección de campeón)."""
        if not (pos and rival):
            return None
        mias = set(self.cuentas)
        pool = [(a, p) for a, p in self.pool() if p == pos]
        if not pool:
            return None
        registros = {a: self.duelos.duelo(a, pos, rival, excluir=mias) for a, _ in pool}
        filas = an.pool_contra(pool, pos, rival, registros, self.mis_partidas(cola), mias, du.MIN_GRUPO)
        for f in filas:
            f.update(nombre=self.datos.nombre(f["campeon"]), icono=self.datos.icono(f["campeon"]))
        return {
            "rival": self.datos.nombre(rival),
            "icono_rival": self.datos.icono(rival),
            "pos": an.NOMBRE_POS.get(pos, pos),
            "filas": filas,
        }

    def _resolver_referencia(self, rid):
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

    def _referencias(self):
        """Para el recolector: los jugadores de referencia con su región y el campeón con el que te comparas
        (None en el perfil de base: interesan todas sus partidas)."""
        pares = [(int(c), rid) for c, rid in (self.cfg.get("referencias") or {}).items()]
        if self.cfg.get("comparar_con") == "perfil" and self.cfg.get("perfil_base"):
            pares.append((None, self.cfg["perfil_base"]))
        out = []
        for campeon, rid in pares:
            info = self.duelos.kv_get(f"ref:{rid.lower()}")
            if info:
                out.append({"puuid": info["puuid"], "region": rec.REGION_DE[info["plataforma"]], "campeon": campeon})
        return out

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
            return self.duelos.campeon(a, pos, de_nivel - mias), self.COMPARAR_CON[modo]
        if registros is None:
            registros = self.duelos.duelo(a, pos, b, excluir=mias)
        return [r for r in registros if r["g"]], "Ganan este duelo"

    def _estado_recolector(self):
        if time.time() - self._resumen_duelos[0] > 30:
            r = self.duelos.resumen()
            r["activo"] = bool(self.recolector)
            r["pool"] = [{"campeon": self.datos.nombre(c), "pos": an.NOMBRE_POS.get(p, p)} for c, p in self.pool()]
            self._resumen_duelos = (time.time(), r)
        return self._resumen_duelos[1]

    def _bucle(self, paso, pausa):
        while True:
            try:
                paso()
            except ClaveInvalida as e:
                self.error_clave = str(e)
            except ErrorRiot as e:
                print(e)
            except Exception:
                traceback.print_exc()
            time.sleep(pausa)

    def _fallo_tarea(self, e):
        if isinstance(e, ClaveInvalida):
            self.error_clave = str(e)
        elif isinstance(e, ErrorRiot):
            print(e)
        else:
            traceback.print_exception(e)

    # --- clave y cuentas -----------------------------------------------------------------
    def _comprobar_clave(self):
        """Prueba la clave con la cuenta principal. Si el PUUID ha cambiado, la caché ya no vale."""
        self._ultima_prueba_clave = time.time()
        if not self.cfg["cuentas"]:
            # Primera vez: las cuentas salen del cliente al abrirlo. De momento basta con saber que la clave vale.
            self.cliente.comprobar()
            return
        principal = self.cfg["cuentas"][0]
        nombre, _, tag = principal.partition("#")
        cuenta = self.cliente.cuenta_por_riot_id(nombre, tag)
        if cuenta:
            guardada = self.cache.kv_get(f"cuenta:{principal.lower()}")
            if guardada and guardada["puuid"] != cuenta["puuid"]:
                print("La clave pertenece a otra aplicación: los PUUID han cambiado y se vacía la caché")
                self.cache.vaciar()
                self.cuentas.clear()
            puuid, visible = self._registrar(principal, cuenta)
            self.cuentas[puuid] = visible
        for rid in self.cfg["cuentas"][1:]:
            self._puuid_de(rid)

    def _registrar(self, rid, cuenta):
        visible = f"{cuenta.get('gameName', rid.partition('#')[0])}#{cuenta.get('tagLine', rid.partition('#')[2])}"
        self.cache.kv_set(f"cuenta:{rid.lower()}", {"puuid": cuenta["puuid"], "rid": visible})
        return cuenta["puuid"], visible

    def _resolver(self, rid):
        """Riot ID -> (puuid, 'Nombre#TAG') o None si no existe."""
        guardada = self.cache.kv_get(f"cuenta:{rid.lower()}")
        if guardada:
            return guardada["puuid"], guardada["rid"]
        nombre, _, tag = rid.partition("#")
        if not nombre or not tag:
            return None
        cuenta = self.cliente.cuenta_por_riot_id(nombre.strip(), tag.strip())
        return self._registrar(rid, cuenta) if cuenta else None

    def _puuid_de(self, rid, recordar=False):
        """Resuelve una cuenta propia y la apunta como tal; con recordar, también en config.json."""
        r = self._resolver(rid)
        if not r:
            return None
        self.cuentas[r[0]] = r[1]
        if recordar and r[1].lower() not in {c.lower() for c in self.cfg["cuentas"]}:
            self.cfg["cuentas"] = [*self.cfg["cuentas"], r[1]]
            self._guardar_cfg(self.cfg)
        return r[0]

    def poner_clave(self, clave):
        clave = clave.strip()
        if not clave.startswith("RGAPI-"):
            return {"ok": False, "error": "Eso no parece una clave de Riot (empiezan por RGAPI-)."}
        config.guardar_clave(clave)
        try:
            self._comprobar_clave()
        except ClaveInvalida:
            self.error_clave = "Clave guardada. Riot tarda un par de minutos en activar las nuevas; se reintenta sola."
            return {"ok": True, "pendiente": True}
        except ErrorRiot as e:
            return {"ok": False, "error": str(e)}
        self._clave_recuperada()
        return {"ok": True}

    def _clave_recuperada(self):
        self.error_clave = ""
        if self._ultimo_juego and self.sesion and not self.sesion.terminada:
            self._abrir(*self._ultimo_juego, forzar=True)

    # --- vigilancia del cliente ------------------------------------------------------------
    def _paso(self):
        ahora = time.time()
        if self.error_clave:
            if ahora - self._ultima_prueba_clave < 20:
                return
            self._comprobar_clave()
            self._clave_recuperada()

        est = self.lcu.estado()
        if not est:
            self._plataforma_vista = False
            self.fase = None
            self.seleccion = None
            self.actualizar_modo()
            self.cliente.limitador.tope_fondo = 40
            # Sin cliente a la vista (p. ej. instalado en otra ruta) se pregunta a Riot de vez en cuando.
            if not self._fijada and ahora - self._ultimo_sondeo >= 45:
                self._ultimo_sondeo = ahora
                for puuid in list(self.cuentas):
                    juego = self.cliente.partida_activa(puuid)
                    if juego:
                        self._abrir(juego, puuid, "propia")
                        return
                self._terminar()
            return

        if not self._plataforma_vista:
            self._plataforma_vista = True
            self._ajustar_plataforma(self.lcu.plataforma())
            if self.recolector is None and self._arranco:
                self._arrancar_recolector()
        anterior, self.fase = self.fase, est["fase"]
        self.cliente.limitador.tope_fondo = 0 if self.fase in PARTIDA_CERCA else 85
        if est["nombre"] and est["tag"]:
            self.cuenta_activa = self._puuid_de(f"{est['nombre']}#{est['tag']}", recordar=True) or self.cuenta_activa
        self.seleccion = self._leer_seleccion() if self.fase == "ChampSelect" else None
        self.actualizar_modo()

        if self.fase in EN_JUEGO:
            if anterior not in EN_JUEGO:
                self._fijada = False  # partida nueva: manda la propia
                # Si no se sabe el mapa se graba igual: mejor una grabación de más que una de menos.
                if self.grabador and self.lcu.mapa() in (0, GRIETA):
                    self.grabador.armar()
            viva = self.sesion and self.sesion.origen == "propia" and not self.sesion.terminada
            if not viva and not self._fijada and self.cuenta_activa and ahora - self._ultimo_sondeo >= 5:
                self._ultimo_sondeo = ahora
                juego = self.cliente.partida_activa(self.cuenta_activa)
                if juego:
                    self._abrir(juego, self.cuenta_activa, "propia")
        else:
            self._terminar()

    def _ajustar_plataforma(self, plataforma):
        """La región de la API sale del cliente del LoL (para quien no juega en EUW)."""
        if not plataforma or plataforma == self.cfg.get("plataforma"):
            return
        region = rec.REGION_DE.get(plataforma)
        if not region:
            return
        print(f"El cliente es de {plataforma}: uso esa región")
        self.cfg.update(plataforma=plataforma, region=region)
        self._guardar_cfg(self.cfg)
        self.cliente.poner_plataforma(plataforma, region)

    def _terminar(self):
        """La partida propia ha acabado: el panel se queda a la vista y se prepara la revisión."""
        s = self.sesion
        if not s or s.origen != "propia" or s.terminada:
            return
        s.terminada = True
        if s.mapa != GRIETA or not self.cfg.get("revisar", True):
            return
        panel = s.panel()
        carpeta = self.grabador.carpeta_reciente() if self.grabador else None
        threading.Thread(target=self._revisar, args=(s.id, s.yo, panel, carpeta), name="revision", daemon=True).start()

    def _revisar(self, game_id, puuid, panel, carpeta, intentos=20, pausa=60):
        """Espera a que Riot publique la partida (tarda unos minutos), la revisa y la guarda."""
        self.revisando += 1
        try:
            return self._revisar_partida(game_id, puuid, panel, carpeta, intentos, pausa)
        finally:
            self.revisando -= 1

    def _revisar_partida(self, game_id, puuid, panel, carpeta, intentos, pausa):
        # El host es "euw1.api.riotgames.com"; el id de la partida empieza por "EUW1_".
        id_ = f"{self.cliente.plataforma.split('.')[0].upper()}_{game_id}"
        crudo = linea = None
        for intento in range(intentos):
            try:
                crudo = self.cliente.partida(id_, fondo=True)
                linea = self.cliente.linea(id_, fondo=True) if crudo else None
            except ErrorRiot as e:
                print(f"Revisión de {id_}: {e}")
            if crudo and linea:
                break
            if intento < intentos - 1:
                time.sleep(pausa)
        if not (crudo and linea):
            return None
        red = an.reducir_partida(crudo)
        if red["remake"]:
            return None
        id_ = red["id"]
        self.cache.guardar_partida(red)
        inicio = crudo["info"].get("gameStartTimestamp")
        desfase = _desfase(carpeta, inicio)
        rev = rv.revisar(red, rv.reducir_linea_completa(linea), puuid, self.datos.nombre, panel, desfase)
        if not rev:
            return None
        rev["referencia"] = self._referencia_revision(crudo, linea, puuid)
        rev["lp"] = self._cambio_lp(puuid, panel, red["cola"])
        rev["carpeta"] = str(carpeta) if carpeta else ""
        rev["icono"] = self.datos.icono(rev["campeon_id"])
        self._guardar_revision(rev)
        if carpeta:
            try:
                (carpeta / "panel.json").write_text(json.dumps(panel, ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError as e:
                print(f"No se pudo guardar el panel junto a la grabación: {e}")
        self.ultima_revision = id_
        print(f"Revisión lista: {id_}")
        if carpeta and desfase is not None and rev["muertes"]:
            threading.Thread(target=self._hacer_clips, args=(rev["id"], desfase), name="clips", daemon=True).start()
        return rev

    def _guardar_revision(self, rev):
        self.cache.kv_set(f"revision:{rev['id']}", rev)
        indice = [r for r in (self.cache.kv_get("revisiones") or []) if r["id"] != rev["id"]]
        claves = ("id", "fecha", "cola", "duracion", "gana", "campeon", "campeon_id", "kda", "icono")
        fila = {k: rev[k] for k in claves}
        fila["lp"] = (rev.get("lp") or {}).get("cambio")
        indice.insert(0, fila)
        indice.sort(key=lambda r: r["fecha"], reverse=True)
        self.cache.kv_set("revisiones", indice[:100])
        if rev.get("carpeta"):
            try:
                (Path(rev["carpeta"]) / "revision.json").write_text(
                    json.dumps(rev, ensure_ascii=False, indent=1), encoding="utf-8"
                )
            except OSError as e:
                print(f"No se pudo guardar la revisión junto a la grabación: {e}")

    def _cambio_lp(self, puuid, panel, cola):
        """Tu liga después de la partida y, si la de antes es de justo una partida atrás, los LP ganados o perdidos."""
        tipo = {420: "RANKED_SOLO_5x5", 440: "RANKED_FLEX_SR"}.get(cola)
        if not tipo:
            return None
        try:
            entradas = self.cliente.ligas(puuid) or []
        except ErrorRiot as e:
            print(f"No se pudo leer la liga tras la partida: {e}")
            return None
        e = next((x for x in entradas if x.get("queueType") == tipo), None)
        if not e:
            return None
        despues = {
            "nivel": e.get("tier", ""),
            "rank": e.get("rank", ""),
            "lp": e.get("leaguePoints", 0),
            "v": e.get("wins", 0),
            "d": e.get("losses", 0),
        }
        out = {"lp": despues["lp"], "nivel": despues["nivel"].lower(), "rank": despues["rank"]}
        yo = next((f for f in ((panel or {}).get("equipos") or {}).get("aliado", []) if f.get("soy_yo")), None)
        antes = ((yo or {}).get("liga") or {}).get("solo" if cola == 420 else "flex")
        if antes and "rank" in antes and despues["v"] + despues["d"] - antes["v"] - antes["d"] == 1:
            a = an.valor_liga(antes["nivel"], antes["rank"], antes["lp"])
            b = an.valor_liga(despues["nivel"], despues["rank"], despues["lp"])
            if a is not None and b is not None:
                out["cambio"] = b - a
        return out

    def _hacer_clips(self, id_, desfase):
        """Recorta cada muerte de la grabación. Si empieza otra partida, espera a que acabe para no quitarle rendimiento."""
        ffmpeg = buscar_ffmpeg()
        if not ffmpeg:
            return
        rev = self.revision(id_)
        for i, m in enumerate(rev["muertes"] if rev else []):
            while self.fase in EN_JUEGO:
                time.sleep(30)
            ruta = clips.recortar(ffmpeg, rev["carpeta"], i, m, desfase)
            if ruta:
                m["clip"] = str(ruta)
        if rev and any(m.get("clip") for m in rev["muertes"]):
            self._guardar_revision(rev)
            print(f"Clips de las muertes de {id_} listos")

    def abrir_clip(self, id_, i):
        rev = self.revision(id_) or {}
        muertes = rev.get("muertes") or []
        ruta = Path(muertes[i].get("clip") or "") if isinstance(i, int) and 0 <= i < len(muertes) else None
        if not ruta or not ruta.is_file():
            return {"ok": False, "error": "Ese clip no está (¿se borró la grabación?)."}
        os.startfile(ruta)
        return {"ok": True}

    def rellenar_revisiones(self):
        """Las revisiones de antes del mapa de muertes no guardaban dónde moriste: se completa una vez."""
        if self.cache.kv_get("relleno_muertes_v1"):
            return
        for fila in self.cache.kv_get("revisiones") or []:
            rev = self.revision(fila["id"])
            if not rev or "equipo" in rev:
                continue
            partida = self.cache.partida(rev["id"])
            yo = next((j for j in (partida or {}).get("jug", []) if j["puuid"] in self.cuentas), None)
            if not yo:
                continue
            try:
                linea = self.cliente.linea(rev["id"], fondo=True)
            except ErrorRiot as e:
                print(f"Relleno de {rev['id']}: {e}")
                return
            if not linea:
                continue
            kills = {k[0]: k for k in rv.reducir_linea_completa(linea)["kills"] if k[4] == yo["pid"]}
            for m in rev["muertes"]:
                k = kills.get(m.get("ms"))
                if k:
                    m["x"], m["y"] = k[1], k[2]
            rev["equipo"] = yo["equipo"]
            self.cache.kv_set(f"revision:{rev['id']}", rev)
        self.cache.kv_set("relleno_muertes_v1", True)

    def _referencia_revision(self, crudo, linea, puuid):
        try:
            registros = du.extraer(crudo, linea, self.datos.legendarios)
        except (KeyError, TypeError, IndexError):
            return None
        mio = next((r for r in registros if r.get("puuid") == puuid), None)
        if registros:
            self.duelos.guardar(crudo["metadata"]["matchId"], [dict(r) for r in registros])
        if not mio:
            return None
        ref, nombre = self.referencia(mio["a"], mio["pos"], mio["b"])
        return du.comparar([mio], ref, mio["pos"], nombre, minimo=3)

    # --- ajustes -----------------------------------------------------------------------------------
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
    COMPARAR_CON = {
        "perfil": "Un jugador (tu perfil de referencia)",
        "ganan": "Los que ganan este duelo",
        "challenger": "Challenger",
        "gm": "Gran Maestro o más",
        "mis_victorias": "Tus victorias",
    }

    def ajustes(self):
        campeones = sorted(({"id": i, "nombre": c["nombre"]} for i, c in self.datos.campeones.items()), key=lambda c: c["nombre"])
        partidas = {}
        for campeon, rid in (self.cfg.get("referencias") or {}).items():
            info = self.duelos.kv_get(f"ref:{rid.lower()}")
            partidas[campeon] = len(self.duelos.de({info["puuid"]}, int(campeon), None)) if info else None
        perfil = self.cfg.get("perfil_base")
        info = self.duelos.kv_get(f"ref:{perfil.lower()}") if perfil else None
        perfil_partidas = len(self.duelos.vistas_de(info["puuid"])) if info else None
        return {
            **{k: self.cfg.get(k) for k in self.EDITABLES},
            "campeones": campeones,
            "opciones_comparar": self.COMPARAR_CON,
            "referencias_partidas": partidas,
            "perfil_partidas": perfil_partidas,
            "version": self.actualizador.estado,
        }

    def guardar_ajustes(self, cambios):
        nuevo = {}
        try:
            if "cuentas" in cambios:
                cuentas = [str(c).strip() for c in cambios["cuentas"] if str(c).strip()]
                if not cuentas or any("#" not in c for c in cuentas):
                    return {"ok": False, "error": "Las cuentas van como Nombre#TAG, y al menos una."}
                nuevo["cuentas"] = cuentas
            if "recordatorios" in cambios:
                nuevo["recordatorios"] = [str(r).strip()[:160] for r in cambios["recordatorios"] if str(r).strip()][:8]
            if "notas" in cambios:
                nuevo["notas"] = {str(int(k)): str(v).strip()[:300] for k, v in dict(cambios["notas"]).items() if str(v).strip()}
            for k in ("grabar", "overlay", "siempre_en_marcha"):
                if k in cambios:
                    nuevo[k] = bool(cambios[k])
            if "comparar_con" in cambios:
                if cambios["comparar_con"] not in self.COMPARAR_CON:
                    return {"ok": False, "error": "Esa referencia no existe."}
                nuevo["comparar_con"] = cambios["comparar_con"]
            if "perfil_base" in cambios:
                nuevo["perfil_base"] = str(cambios["perfil_base"]).strip()
                if nuevo["perfil_base"]:
                    error = self._resolver_referencia(nuevo["perfil_base"])
                    if error:
                        return {"ok": False, "error": error}
            if (nuevo.get("comparar_con") or self.cfg.get("comparar_con")) == "perfil" and not nuevo.get(
                "perfil_base", self.cfg.get("perfil_base")
            ):
                return {"ok": False, "error": "Para compararte con un jugador, escribe su Nombre#TAG en el perfil de referencia."}
            if "referencias" in cambios:
                refs = {}
                for campeon, rid in dict(cambios["referencias"]).items():
                    rid = str(rid).strip()
                    if not rid:
                        continue
                    error = self._resolver_referencia(rid)
                    if error:
                        return {"ok": False, "error": error}
                    refs[str(int(campeon))] = rid
                nuevo["referencias"] = refs
            if "grabacion_codificador" in cambios:
                if cambios["grabacion_codificador"] not in ("auto", "cpu"):
                    return {"ok": False, "error": "Codificador desconocido."}
                nuevo["grabacion_codificador"] = cambios["grabacion_codificador"]
            if "grabacion_max_gb" in cambios:
                nuevo["grabacion_max_gb"] = max(0, int(float(cambios["grabacion_max_gb"] or 0)))
            if "atajo_overlay" in cambios:
                if not parsear_atajo(str(cambios["atajo_overlay"])):
                    return {"ok": False, "error": "No entiendo ese atajo. Ejemplos: ctrl+tab, alt+x, f9."}
                nuevo["atajo_overlay"] = str(cambios["atajo_overlay"]).strip().lower()
            if "overlay_opacidad" in cambios:
                nuevo["overlay_opacidad"] = min(1.0, max(0.4, float(cambios["overlay_opacidad"])))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Algún valor no tiene el formato esperado."}
        if "siempre_en_marcha" in nuevo and nuevo["siempre_en_marcha"] != self.cfg.get("siempre_en_marcha"):
            error = self._arranque_windows(nuevo["siempre_en_marcha"])
            if error:
                return {"ok": False, "error": error}
        self.cfg.update(nuevo)
        self._guardar_cfg(self.cfg)
        self._duelos_cache.clear()
        if "grabar" in nuevo:
            self.grabador = (self.grabador or Grabador(self.cfg)) if nuevo["grabar"] else None
        for rid in nuevo.get("cuentas", []):
            threading.Thread(target=self._puuid_de, args=(rid,), daemon=True).start()
        if self.sesion:
            self.sesion._sucio = True  # las notas y las reglas nuevas salen ya en el panel
        return {"ok": True}

    def salir(self):
        """Cierra la app del todo (con 'siempre en marcha' no se cierra sola)."""
        if not self.al_salir:
            return {"ok": False, "error": "Sin ventanas no puedo cerrarme desde aquí."}
        threading.Timer(0.5, self.al_salir).start()
        return {"ok": True}

    def notas_de(self, campeones, rivales=()):
        """Tus notas de los campeones que hay en la partida (las escribiste tú antes de jugar)."""
        notas = self.cfg.get("notas") or {}
        vistos, out = set(), []
        for c in campeones:
            if c and c not in vistos and notas.get(str(c)):
                vistos.add(c)
                out.append(
                    {"campeon": self.datos.nombre(c), "icono": self.datos.icono(c), "texto": notas[str(c)], "rival": c in rivales}
                )
        return out

    def revisiones(self):
        hora = lambda ms: datetime.datetime.fromtimestamp(ms / 1000).hour  # noqa: E731
        lista = self.cache.kv_get("revisiones") or []
        return {
            "lista": lista,
            "tendencias": rv.tendencias(self._todas_mis_partidas(), set(self.cuentas), self.datos.nombre, hora),
            "muertes": rv.mapa_muertes(self.revision(f["id"]) for f in lista),
        }

    def revision(self, id_):
        return self.cache.kv_get(f"revision:{id_}")

    def abrir_carpeta(self, id_):
        rev = self.revision(id_) or {}
        carpeta = Path(rev.get("carpeta") or "")
        if not rev.get("carpeta") or not carpeta.is_dir():
            return {"ok": False, "error": "Esa partida no tiene grabación."}
        os.startfile(carpeta)
        return {"ok": True}

    def actualizar_modo(self):
        """Pantalla de carga o juego empezado, según el reloj del propio juego (el overlay lo llama más a menudo)."""
        if self.fase not in EN_JUEGO:
            self.modo, self.reloj = "previa", None
            return
        self.reloj = self.lcu.reloj()
        self.modo = "juego" if self.reloj else "carga"

    def _abrir(self, juego, yo, origen, forzar=False):
        with self._lock:
            s = self.sesion
            if s and not forzar and s.id == juego.get("gameId") and s.yo == yo:
                s.terminada = False
                return
            if s:
                s.cancelar()
            self._ultimo_juego = (juego, yo, origen)
            # Se lanza antes de publicarla: así nadie pide su panel mientras se tiene este cerrojo.
            nueva = Sesion(self, juego, yo, origen)
            nueva.lanzar()
            self.sesion = nueva

    def buscar(self, rid):
        """Abre a mano la partida en vivo de cualquier jugador."""
        try:
            r = self._resolver(rid.strip())
            if not r:
                return {"ok": False, "error": "No encuentro esa cuenta. Formato: Nombre#TAG"}
            juego = self.cliente.partida_activa(r[0])
        except ClaveInvalida as e:
            self.error_clave = str(e)
            return {"ok": False, "error": str(e)}
        except ErrorRiot as e:
            return {"ok": False, "error": str(e)}
        if not juego:
            return {"ok": False, "error": f"{r[1]} no está en partida ahora mismo."}
        self._fijada = True
        self._abrir(juego, r[0], "propia" if r[0] in self.cuentas else "manual")
        return {"ok": True}

    def volver(self):
        """Deja de mostrar la partida buscada a mano."""
        with self._lock:
            self._fijada = False
            if self.sesion and self.sesion.origen == "manual":
                self.sesion.cancelar()
                self.sesion = None
        return {"ok": True}

    # --- datos compartidos ------------------------------------------------------------------
    def _una_vez(self, clave, fn):
        """Evita pedir lo mismo dos veces a la vez (dos jugadores que comparten partida)."""
        with self._lock:
            evento = self._en_curso.get(clave)
            mio = evento is None
            if mio:
                evento = self._en_curso[clave] = threading.Event()
        if not mio:
            evento.wait(60)
            return
        try:
            fn()
        finally:
            evento.set()
            with self._lock:
                self._en_curso.pop(clave, None)

    def traer_partida(self, id_, cancelada=None, fondo=False):
        def pedir():
            if self.cache.partida(id_):
                return
            m = self.cliente.partida(id_, fondo=fondo, cancelada=cancelada)
            if m:
                try:
                    self.cache.guardar_partida(an.reducir_partida(m))
                except (KeyError, TypeError) as e:
                    print(f"Partida {id_} con formato inesperado: {e!r}")

        if not self.cache.partida(id_):
            self._una_vez(f"p:{id_}", pedir)
        return self.cache.partida(id_)

    def traer_linea(self, id_, cancelada=None):
        def pedir():
            if self.cache.linea(id_):
                return
            t = self.cliente.linea(id_, cancelada=cancelada)
            if t:
                try:
                    self.cache.guardar_linea(an.reducir_linea(t))
                except (KeyError, TypeError) as e:
                    print(f"Línea de tiempo {id_} con formato inesperado: {e!r}")

        if not self.cache.linea(id_):
            self._una_vez(f"l:{id_}", pedir)
        return self.cache.linea(id_)

    def mis_partidas(self, cola=None):
        """Clasificatorias propias de la temporada, de la más reciente a la más antigua.

        Con cola 420 o 440 devuelve solo las de esa cola.
        """
        mias = self._todas_mis_partidas()
        return [m for m in mias if m["cola"] == cola] if cola in LIGA_COLA else mias

    def _todas_mis_partidas(self):
        with self._lock:
            marca = (tuple(sorted(self.cuentas)), self.sync["hechas"], int(time.time() // 30))
            if self._mias[0] == marca:
                return self._mias[1]
            vistas, mias = set(), []
            for puuid in self.cuentas:
                for m in self.cache.partidas_de(puuid, desde=self.inicio_temporada_ms):
                    if m["id"] not in vistas and m["cola"] in LIGA_COLA:
                        vistas.add(m["id"])
                        mias.append(m)
            mias.sort(key=lambda m: m["creacion"], reverse=True)
            self._mias = (marca, mias)
            return mias

    # --- selección de campeón ------------------------------------------------------------------
    def _leer_seleccion(self):
        s = self.lcu.seleccion()
        if not s:
            return None
        clave = (s["mio"], tuple(s["rivales"]), s["cola"], s.get("pos", ""))
        if clave == self._sel_clave and self.seleccion:
            return self.seleccion
        self._sel_clave = clave
        datos = self.datos
        pos = s.get("pos", "")
        rival = an.rival_probable(s["rivales"], pos, datos.roles) if pos else None
        rivales = [{"campeon": c, "pos": pos if c == rival else "", "nombre_campeon": datos.nombre(c)} for c in s["rivales"]]
        h = an.mi_historial(
            set(self.cuentas), self.mis_partidas(s["cola"]), s["mio"], rivales, {}, int(time.time() * 1000), mi_pos=pos
        )
        h["cola_txt"] = NOMBRE_LIGA.get(s["cola"], "")
        for fila in h["vs"]:
            fila["icono"] = datos.icono(fila["campeon"])
        return {
            "duelo": self.duelo(s["mio"], pos, rival) if s["mio"] and rival else None,
            "pool": self.pool_contra(pos, rival, s["cola"]),
            "pos": an.NOMBRE_POS.get(pos, ""),
            "mio": {"nombre": datos.nombre(s["mio"]), "icono": datos.icono(s["mio"]), "splash": datos.splash(s["mio"])}
            if s["mio"]
            else None,
            "historial": h,
            "notas": self.notas_de([s["mio"], *s["rivales"]], rivales=set(s["rivales"])),
        }

    # --- historial propio en segundo plano ---------------------------------------------------------
    def _cargando(self):
        s = self.sesion
        return bool(s and not s.terminada and s.hechas < s.total)

    def _fondo(self):
        if self.error_clave or self._cargando():
            return
        for puuid in list(self.cuentas):
            self._sincronizar(puuid)
        if self.cuentas and self.fase not in EN_JUEGO:
            self.rellenar_revisiones()

    def _sincronizar(self, puuid):
        """Baja las clasificatorias de la temporada de una cuenta propia, sin estorbar a una partida en curso."""
        if self.cache.kv_get(f"sync:{puuid}", max_edad=1800) is not None:
            return
        ids, inicio = [], 0
        while True:
            pagina = self.cliente.ids_partidas(
                puuid, tipo="ranked", inicio=inicio, n=100, desde=self.inicio_temporada_ms // 1000, fondo=True
            )
            ids += pagina
            if len(pagina) < 100 or inicio >= 900:
                break
            inicio += 100
        faltan = [i for i in ids if not self.cache.partida(i)]
        self.sync = {"hechas": 0, "total": len(faltan)}
        for id_ in faltan:
            while self._cargando():
                time.sleep(2)
            self.traer_partida(id_, fondo=True)
            self.sync["hechas"] += 1
        self.cache.kv_set(f"sync:{puuid}", len(ids))

    # --- estado para el panel ------------------------------------------------------------------------
    def _para_el_modo(self, panel):
        """Con el juego ya empezado, solo datos: fuera el plan y los veredictos de línea.

        Riot no permite que una app saque conclusiones por el jugador durante la partida; antes de empezar
        (selección y pantalla de carga) sí se pueden enseñar.
        """
        if self.modo != "juego":
            return panel
        # Los colores de alerta también son una lectura: en juego todo va en neutro.
        jungla = panel.get("jungla")
        if jungla:
            # El mapa de dónde suele estar en los primeros minutos se queda fuera: ya jugando, se parecería a seguirle.
            jungla = dict(jungla, tarjetas=[dict(t, tono="neutro") for t in jungla["tarjetas"]], mapa={})
        return dict(
            panel,
            plan=[],
            lineas=[dict(l, veredicto="", tono="neutro") for l in panel["lineas"]],
            avisos=[dict(a, tono="neutro") for a in panel["avisos"]],
            jungla=jungla,
            duelo=None,  # lo que hacen los que ganan el duelo es una lectura: solo antes de empezar
        )

    def _estado_overlay(self):
        if not self.cfg.get("overlay", True):
            return {"activo": False, "atajo": "", "aviso": ""}
        leido, modo = self._ventana_juego
        if time.time() - leido > 30:
            modo = modo_ventana(self.lcu.ruta)
            self._ventana_juego = (time.time(), modo)
        aviso = ""
        if modo is not None and modo != MODO_SIN_BORDES:
            aviso = "El juego no está en ventana sin bordes: el panel no puede salir encima. Cámbialo en Opciones > Vídeo > Modo de ventana."
        return {"activo": True, "atajo": self.cfg.get("atajo_overlay", ""), "aviso": aviso}

    def estado(self, contar=True):
        # El overlay también pide el estado, pero estar escondido encima del juego no es "mirar el panel".
        if contar:
            self.ultima_consulta = time.time()
        s = self.sesion
        limitador = self.cliente.limitador
        return {
            "fase": self.fase,
            "fase_txt": FASES.get(self.fase, self.fase) if self.fase else "Cliente del LoL cerrado",
            "modo": self.modo,
            "reloj": self.reloj,
            "overlay": self._estado_overlay(),
            "cuenta": self.cuentas.get(self.cuenta_activa, ""),
            "clave": {"ok": not self.error_clave, "error": self.error_clave},
            "cuota": limitador.estado(self.cliente.region),
            "sync": self.sync,
            "grabacion": self.grabador.estado() if self.grabador else None,
            "ultima_revision": self.ultima_revision,
            "seleccion": self.seleccion,
            "recolector": self._estado_recolector(),
            "version": self.actualizador.estado,
            "novedades": self.actualizador.novedades(),
            "panel": self._para_el_modo(s.panel()) if s else None,
        }
