"""Recolector de duelos: partidas de Master+ con línea de tiempo en las que sale tu campeón en tu rol.

Corea, Norteamérica y Asia-Pacífico tienen cuota propia (Riot cuenta cada host aparte), así que no le
quitan nada al panel de tu partida. EUW comparte cuota con el panel: solo se usa con el cliente quieto
y empieza por tus propias partidas (para comparar tus números con los de Master+).

Uso suelto (sin la app): py -m deepprep.recolector [--minutos 60] [--sin-europa]
"""

import msvcrt
import random
import sys
import threading
import time
from collections import deque

from . import analisis as an
from . import config
from . import duelos as du
from .base_duelos import BaseDuelos
from .constantes import DURACION_MINIMA_S, SOLO_DUO
from .riot import ClaveInvalida, Cliente, ErrorRiot

RUTA_CERROJO = config.DATOS / "recolector.lock"
NIVEL_LIGA = {"challengerleagues": "CHALLENGER", "grandmasterleagues": "GRANDMASTER", "masterleagues": "MASTER"}
# (plataforma, región) con su propia cuota. EUW va aparte: comparte cuota con el panel.
TODAS = [("euw1", "europe"), ("kr", "asia"), ("na1", "americas"), ("vn2", "sea")]
REGIONES = [r for r in TODAS if r[1] != "europe"]  # las de fuera, para quien juega en EUW
LIGAS = ("challengerleagues", "grandmasterleagues", "masterleagues")
DIAS = 45  # solo partidas recientes: el juego cambia con los parches
PARTIDAS_SEMILLA = 4  # de cada jugador cualquiera se miran pocas; de uno que juega tu campeón, todas


class Recolector:
    """Un hilo por región. 'pool' y 'puede_europa' son funciones: se consultan en cada vuelta."""

    def __init__(
        self,
        base,
        leer_clave,
        legendarios,
        pool,
        mis_partidas=list,
        mis_puuids=lambda: set(),
        cliente_europa=None,
        puede_europa=lambda: False,
        regiones=REGIONES,
        referencias=list,
    ):
        self.base = base
        self.legendarios = legendarios
        self.pool = pool
        self.mis_partidas = mis_partidas
        self.mis_puuids = mis_puuids
        self.puede_europa = puede_europa
        self.referencias = referencias  # [{'puuid', 'region', 'campeon'}]: jugadores con los que te comparas
        cfg = config.cargar()
        self.clientes = [Cliente(dict(cfg, plataforma=p, region=r), leer_clave) for p, r in regiones]
        self.cliente_europa = cliente_europa
        self.parar = threading.Event()
        self.estado = {"nuevas": 0, "error": ""}
        self._cerrojo = None

    # --- arranque: solo un recolector a la vez (la app o el suelto) --------------------------------
    def arrancar(self):
        cerrojo = None
        try:
            cerrojo = open(RUTA_CERROJO, "w")  # noqa: SIM115  se queda abierto y cogido mientras viva el recolector
            msvcrt.locking(cerrojo.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            if cerrojo:
                cerrojo.close()
            print("Ya hay otro recolector en marcha; este no arranca")
            return False
        self._cerrojo = cerrojo
        for c in self.clientes:
            threading.Thread(target=self._bucle, args=(c, False), name=f"recolector-{c.region}", daemon=True).start()
        if self.cliente_europa:
            threading.Thread(target=self._bucle, args=(self.cliente_europa, True), name="recolector-europe", daemon=True).start()
        return True

    def _bucle(self, cliente, europa):
        while not self.parar.is_set():
            try:
                if europa:
                    if not self.puede_europa():
                        self.parar.wait(30)
                        continue
                    self._mias(cliente)
                self._vuelta(cliente, europa)
            except ClaveInvalida as e:
                self.estado["error"] = str(e)
                self.parar.wait(300)
            except ErrorRiot as e:
                print(f"Recolector {cliente.region}: {e}")
                self.parar.wait(30)
            except Exception as e:  # noqa: BLE001  un fallo raro no debe parar la recogida para siempre
                print(f"Recolector {cliente.region}: {e!r}")
                self.parar.wait(60)

    def _cancelada(self, europa):
        """En EUW, lo que pide el recolector se deja a medias en cuanto el panel necesita la cuota."""
        return (lambda: not self.puede_europa()) if europa else None

    # --- tus partidas (EUW) -----------------------------------------------------------------------------
    def _mias(self, cliente):
        """Línea de tiempo de tus clasificatorias con los campeones de tu pool, para tus números."""
        pool = set(self.pool())
        puuids = self.mis_puuids()
        for m in self.mis_partidas():
            if self.parar.is_set() or not self.puede_europa():
                return
            if m.get("remake") or self.base.vista(m["id"]):
                continue
            yo = next((j for j in m["jug"] if j["puuid"] in puuids), None)
            if not yo or (yo["campeon"], yo["pos"]) not in pool:
                continue
            self._bajar(cliente, m["id"], True, europa=True)

    # --- partidas de Master+ ---------------------------------------------------------------------------
    def _semillas(self, cliente, europa):
        """Jugadores de Master+ de la plataforma; de paso se apunta el nivel de cada uno (para compararte con Challenger)."""
        clave = f"ligas:{cliente.plataforma}"
        ligas = self.base.kv_get(clave, max_edad=86400)
        if not ligas:
            ligas = {}
            for liga in LIGAS:
                datos = cliente.liga_de_elite(liga, fondo=europa, cancelada=self._cancelada(europa)) or {}
                ligas.update({e["puuid"]: NIVEL_LIGA[liga] for e in datos.get("entries", []) if e.get("puuid")})
            self.base.kv_set(clave, ligas)
        return list(ligas)

    def _referencias(self, cliente, europa):
        """Partidas recientes de tus jugadores de referencia que juegan en esta región (cada 6 horas)."""
        region = cliente.region.split(".")[0]
        desde = int(time.time()) - DIAS * 86400
        for ref in self.referencias():
            if ref["region"] != region or self.base.kv_get(f"ref_al_dia:{ref['puuid']}", max_edad=6 * 3600):
                continue
            ids = cliente.ids_partidas(ref["puuid"], cola=SOLO_DUO, n=100, desde=desde, fondo=europa) or []
            for id_ in ids:
                if self.parar.is_set() or (europa and not self.puede_europa()):
                    return
                if self.base.vista(id_):
                    continue
                m = cliente.partida(id_, fondo=europa, cancelada=self._cancelada(europa))
                suyo = next((p for p in (m or {}).get("info", {}).get("participants", []) if p["puuid"] == ref["puuid"]), None)
                # campeon None: perfil de base, valen todas sus partidas.
                otro = ref["campeon"] is not None and suyo and suyo["championId"] != ref["campeon"]
                if not suyo or otro or m["info"].get("gameDuration", 0) < DURACION_MINIMA_S:
                    self.base.marcar(id_, False)
                    continue
                self._bajar(cliente, id_, False, europa, partida=m)
            self.base.kv_set(f"ref_al_dia:{ref['puuid']}", len(ids))

    def _vuelta(self, cliente, europa):
        """Recorre jugadores de Master+; cuando sale alguien con un campeón de tu pool, sigue su historial."""
        semillas = self._semillas(cliente, europa)
        random.shuffle(semillas)
        seguir = deque()  # jugadores que juegan un campeón de tu pool en su posición
        seguidos = set()
        desde = int(time.time()) - DIAS * 86400
        while (seguir or semillas) and not self.parar.is_set():
            if europa and not self.puede_europa():
                return
            self._referencias(cliente, europa)
            pool = set(self.pool())
            if not pool:
                self.parar.wait(60)
                continue
            puuid, todas = (seguir.popleft(), True) if seguir else (semillas.pop(), False)
            ids = cliente.ids_partidas(puuid, cola=SOLO_DUO, n=20, desde=desde, fondo=europa) or []
            for id_ in ids if todas else ids[:PARTIDAS_SEMILLA]:
                if self.parar.is_set() or self.base.vista(id_):
                    continue
                m = cliente.partida(id_, fondo=europa, cancelada=self._cancelada(europa))
                if not m:
                    self.base.marcar(id_, False)
                    continue
                aciertos = [p for p in m["info"]["participants"] if (p["championId"], p.get("teamPosition")) in pool]
                if not aciertos or m["info"].get("gameDuration", 0) < DURACION_MINIMA_S:
                    self.base.marcar(id_, False)
                    continue
                self._bajar(cliente, id_, False, europa, partida=m)
                for p in aciertos:
                    if p["puuid"] not in seguidos:
                        seguidos.add(p["puuid"])
                        seguir.append(p["puuid"])

    def _bajar(self, cliente, id_, mia, europa, partida=None):
        partida = partida or cliente.partida(id_, fondo=europa, cancelada=self._cancelada(europa))
        linea = cliente.linea(id_, fondo=europa, cancelada=self._cancelada(europa)) if partida else None
        if not (partida and linea):
            self.base.marcar(id_, False)
            return
        try:
            registros = du.extraer(partida, linea, self.legendarios)
        except (KeyError, TypeError, IndexError) as e:
            print(f"Partida {id_} con formato inesperado: {e!r}")
            registros = []
        if registros:
            self.base.guardar(id_, registros)
            self.estado["nuevas"] += 1
        else:
            self.base.marcar(id_, False)


def main():
    """Recolector suelto, sin la app (p. ej. para llenar la base de noche)."""
    from .app import crear_app

    minutos = float(sys.argv[sys.argv.index("--minutos") + 1]) if "--minutos" in sys.argv else None
    app = crear_app(grabar=False)
    try:
        app.comprobar_clave()
    except (ClaveInvalida, ErrorRiot) as e:
        print(f"No puedo usar la clave: {e}")
        return
    base = BaseDuelos()
    mias = app.mis_partidas
    rec = Recolector(
        base,
        config.leer_clave,
        app.datos.legendarios,
        pool=lambda: an.pool_de(mias(), set(app.cuentas)),
        mis_partidas=mias,
        mis_puuids=lambda: set(app.cuentas),
        cliente_europa=None if "--sin-europa" in sys.argv else app.cliente,
        puede_europa=lambda: True,
    )
    print("Pool:", [(app.datos.nombre(c), p) for c, p in rec.pool()])
    if not rec.arrancar():
        return
    inicio = time.time()
    try:
        while minutos is None or time.time() - inicio < minutos * 60:
            time.sleep(60)
            print(time.strftime("%H:%M"), base.resumen(), "nuevas:", rec.estado["nuevas"], flush=True)
    except KeyboardInterrupt:
        pass
    rec.parar.set()


if __name__ == "__main__":
    main()
