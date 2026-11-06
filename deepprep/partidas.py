"""Las partidas y líneas de tiempo que usa la app (de la caché o de Riot) y tus clasificatorias de la temporada."""

import datetime
import threading
import time
from typing import Any

from . import analisis as an
from . import recolector as rec
from .constantes import LIGA_COLA

# Tus campeones por posición (el pool) se recalculan como mucho cada tanto.
CADA_POOL_S = 600


class Partidas:
    """Trae partidas y líneas de tiempo sin pedir dos veces la misma a la vez, y lleva tu historial de la temporada.

    cuentas: tus cuentas (puuid -> 'Nombre#TAG'), el mismo diccionario que va llenando Cuentas.
    """

    def __init__(self, cache, cliente, cuentas, inicio_temporada):
        self.cache = cache
        self.cliente = cliente
        self.cuentas = cuentas
        self.inicio_temporada_ms = int(datetime.datetime.fromisoformat(inicio_temporada).timestamp() * 1000)
        self.sync = {"hechas": 0, "total": 0}  # partidas propias que faltan por bajar
        self._lock = threading.RLock()
        self._en_curso: dict[str, threading.Event] = {}
        self._mias: tuple[Any, list[dict[str, Any]]] = (None, [])  # (marca, partidas) de la última vez
        self._pool: tuple[float, list[tuple[int, str]]] = (0.0, [])

    # --- datos compartidos ------------------------------------------------------------------
    def _una_vez(self, clave, fn):
        """Evita pedir lo mismo dos veces a la vez (dos jugadores que comparten partida)."""
        with self._lock:
            evento = self._en_curso.get(clave)
            mio = evento is None
            if evento is None:
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

    # --- tus partidas -------------------------------------------------------------------------
    def mis_partidas(self, cola=None):
        """Clasificatorias propias de la temporada, de la más reciente a la más antigua.

        Con cola 420 o 440 devuelve solo las de esa cola.
        """
        mias = self.todas_mis_partidas()
        return [m for m in mias if m["cola"] == cola] if cola in LIGA_COLA else mias

    def todas_mis_partidas(self):
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

    def pool(self):
        """Tus campeones por posición (de tus clasificatorias de la temporada); se recalcula cada 10 min."""
        if time.time() - self._pool[0] > CADA_POOL_S:
            self._pool = (time.time(), rec.pool_de(self.mis_partidas(), set(self.cuentas)))
        return self._pool[1]

    def sincronizar(self, puuid, ocupada=lambda: False):
        """Baja las clasificatorias de la temporada de una cuenta propia, sin estorbar a una partida en curso.

        ocupada: si hay una partida cargándose; mientras tanto se espera.
        """
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
            while ocupada():
                time.sleep(2)
            self.traer_partida(id_, fondo=True)
            self.sync["hechas"] += 1
        self.cache.kv_set(f"sync:{puuid}", len(ids))
