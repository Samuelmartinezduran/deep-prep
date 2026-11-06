"""Lo común de las bases SQLite de la app (cache.db y duelos.db).

Una conexión que comparten los hilos (con su cerrojo), una tabla kv de valores JSON con la hora a la que se
guardaron (para la caducidad) y los datos grandes guardados como JSON comprimido.
"""

import json
import sqlite3
import threading
import time
import zlib

ESQUEMA_KV = "CREATE TABLE IF NOT EXISTS kv (clave TEXT PRIMARY KEY, valor TEXT NOT NULL, ts REAL NOT NULL);"


def empaquetar(obj):
    return zlib.compress(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def desempaquetar(blob):
    return json.loads(zlib.decompress(blob).decode("utf-8"))


class BaseSQLite:
    """Base SQLite con su tabla kv. ESQUEMA: las tablas propias de cada base, que se crean al abrirla.

    espera: segundos que espera SQLite si otro proceso tiene la base bloqueada.
    """

    ESQUEMA = ""

    def __init__(self, ruta, espera=5.0):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(ruta), check_same_thread=False, timeout=espera)
        with self._lock:
            self._db.executescript(f"PRAGMA journal_mode=WAL;\n{ESQUEMA_KV}\n{self.ESQUEMA}")
            self._db.commit()

    # --- clave/valor con caducidad -------------------------------------------------
    def kv_get(self, clave, max_edad=None):
        with self._lock:
            fila = self._db.execute("SELECT valor, ts FROM kv WHERE clave=?", (clave,)).fetchone()
        if not fila or (max_edad is not None and time.time() - fila[1] > max_edad):
            return None
        return json.loads(fila[0])

    def kv_set(self, clave, valor):
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO kv (clave, valor, ts) VALUES (?,?,?)",
                (clave, json.dumps(valor), time.time()),
            )
            self._db.commit()

    def cerrar(self):
        with self._lock:
            self._db.close()
