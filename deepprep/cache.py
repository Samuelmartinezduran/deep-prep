"""Caché local en SQLite. Las partidas no cambian nunca, así que se guardan para siempre."""
import json
import sqlite3
import threading
import time
import zlib


def _empaquetar(obj):
    return zlib.compress(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _desempaquetar(blob):
    return json.loads(zlib.decompress(blob).decode("utf-8"))


class Cache:
    def __init__(self, ruta):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(ruta), check_same_thread=False)
        self._partidas = {}
        self._lineas = {}
        with self._lock:
            self._db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS kv (clave TEXT PRIMARY KEY, valor TEXT NOT NULL, ts REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS partidas (id TEXT PRIMARY KEY, creacion INTEGER, cola INTEGER, datos BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS partida_jugador (puuid TEXT, id TEXT, creacion INTEGER, cola INTEGER,
                    PRIMARY KEY (puuid, id));
                CREATE INDEX IF NOT EXISTS ix_pj ON partida_jugador (puuid, creacion DESC);
                CREATE TABLE IF NOT EXISTS lineas (id TEXT PRIMARY KEY, datos BLOB NOT NULL);
                """
            )
            self._db.commit()

    # --- clave/valor con caducidad -------------------------------------------------
    def kv_get(self, clave, max_edad=None):
        with self._lock:
            fila = self._db.execute("SELECT valor, ts FROM kv WHERE clave=?", (clave,)).fetchone()
        if not fila:
            return None
        if max_edad is not None and time.time() - fila[1] > max_edad:
            return None
        return json.loads(fila[0])

    def kv_set(self, clave, valor):
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO kv (clave, valor, ts) VALUES (?,?,?)",
                (clave, json.dumps(valor), time.time()),
            )
            self._db.commit()

    # --- partidas ------------------------------------------------------------------
    def partida(self, id_):
        with self._lock:
            if id_ in self._partidas:
                return self._partidas[id_]
            fila = self._db.execute("SELECT datos FROM partidas WHERE id=?", (id_,)).fetchone()
            if not fila:
                return None
            red = _desempaquetar(fila[0])
            self._partidas[id_] = red
            return red

    def guardar_partida(self, red):
        with self._lock:
            self._partidas[red["id"]] = red
            self._db.execute(
                "INSERT OR REPLACE INTO partidas (id, creacion, cola, datos) VALUES (?,?,?,?)",
                (red["id"], red["creacion"], red["cola"], _empaquetar(red)),
            )
            self._db.executemany(
                "INSERT OR REPLACE INTO partida_jugador (puuid, id, creacion, cola) VALUES (?,?,?,?)",
                [(j["puuid"], red["id"], red["creacion"], red["cola"]) for j in red["jug"] if j.get("puuid")],
            )
            self._db.commit()

    def partidas_de(self, puuid, desde=0, limite=1000):
        """Partidas guardadas de un jugador, de la más reciente a la más antigua."""
        with self._lock:
            ids = [
                f[0]
                for f in self._db.execute(
                    "SELECT id FROM partida_jugador WHERE puuid=? AND creacion>=? ORDER BY creacion DESC LIMIT ?",
                    (puuid, desde, limite),
                )
            ]
        return [p for p in (self.partida(i) for i in ids) if p]

    # --- líneas de tiempo ----------------------------------------------------------
    def linea(self, id_):
        with self._lock:
            if id_ in self._lineas:
                return self._lineas[id_]
            fila = self._db.execute("SELECT datos FROM lineas WHERE id=?", (id_,)).fetchone()
            if not fila:
                return None
            red = _desempaquetar(fila[0])
            self._lineas[id_] = red
            return red

    def guardar_linea(self, red):
        with self._lock:
            self._lineas[red["id"]] = red
            self._db.execute("INSERT OR REPLACE INTO lineas (id, datos) VALUES (?,?)", (red["id"], _empaquetar(red)))
            self._db.commit()

    def vaciar(self):
        """Borra todo. Hace falta si cambia la clave de aplicación, porque los PUUID dependen de ella."""
        with self._lock:
            self._partidas.clear()
            self._lineas.clear()
            for tabla in ("kv", "partidas", "partida_jugador", "lineas"):
                self._db.execute(f"DELETE FROM {tabla}")
            self._db.commit()

    def cerrar(self):
        with self._lock:
            self._db.close()
