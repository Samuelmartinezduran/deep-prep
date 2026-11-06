"""La base de duelos (duelos.db): los registros de los duelos de Master+ (y los tuyos) y las partidas ya miradas.

La llena el recolector (y la revisión, con tus partidas) y la leen el comparador y los ajustes. El análisis de un
duelo, con funciones puras, está en duelos.py.
"""

import json
import time

from . import config
from .almacen import BaseSQLite, desempaquetar, empaquetar

RUTA_DB = config.DATOS / "duelos.db"


class BaseDuelos(BaseSQLite):
    """Los registros de duelos de Master+ (y los tuyos), qué partidas ya se han mirado y el clave/valor."""

    ESQUEMA = """
        CREATE TABLE IF NOT EXISTS reg (id TEXT, pos TEXT, a INTEGER, b INTEGER, puuid TEXT, datos BLOB NOT NULL,
            PRIMARY KEY (id, pos, a));
        CREATE INDEX IF NOT EXISTS ix_duelo ON reg (a, pos, b);
        CREATE INDEX IF NOT EXISTS ix_puuid ON reg (puuid, a, pos);
        CREATE TABLE IF NOT EXISTS vista (id TEXT PRIMARY KEY, util INTEGER, ts REAL);
    """

    def __init__(self, ruta=RUTA_DB):
        # El recolector y la app la usan a la vez desde dos procesos (con el recolector suelto): se espera más.
        super().__init__(ruta, espera=30)

    def vista(self, id_):
        with self._lock:
            return self._db.execute("SELECT 1 FROM vista WHERE id=?", (id_,)).fetchone() is not None

    def marcar(self, id_, util):
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO vista VALUES (?,?,?)", (id_, int(util), time.time()))
            self._db.commit()

    def guardar(self, id_, registros):
        with self._lock:
            self._db.executemany(
                "INSERT OR REPLACE INTO reg VALUES (?,?,?,?,?,?)",
                [(id_, r["pos"], r["a"], r["b"], r.pop("puuid", ""), empaquetar(r)) for r in registros],
            )
            self._db.execute("INSERT OR REPLACE INTO vista VALUES (?,?,?)", (id_, 1, time.time()))
            self._db.commit()

    def duelo(self, a, pos, b, excluir=()):
        """Registros de a contra b en pos (de cualquiera menos de las cuentas en excluir); '_p' es el jugador."""
        with self._lock:
            filas = self._db.execute("SELECT puuid, datos FROM reg WHERE a=? AND pos=? AND b=?", (a, pos, b)).fetchall()
        return [dict(desempaquetar(d), _p=p) for p, d in filas if p not in excluir]

    def campeon(self, a, pos, puuids):
        """Registros de ese campeón en esa posición (contra cualquiera) de los jugadores en puuids."""
        with self._lock:
            filas = self._db.execute("SELECT puuid, datos FROM reg WHERE a=? AND pos=?", (a, pos)).fetchall()
        return [dict(desempaquetar(d), _p=p) for p, d in filas if p in puuids]

    def posicion(self, pos, puuids):
        """Registros en esa posición (con cualquier campeón) de los jugadores en puuids."""
        marcas = ",".join("?" * len(puuids))
        with self._lock:
            filas = self._db.execute(
                f"SELECT puuid, datos FROM reg WHERE pos=? AND puuid IN ({marcas})", (pos, *puuids)
            ).fetchall()
        return [dict(desempaquetar(d), _p=p) for p, d in filas]

    def vistas_de(self, puuid):
        """Partidas guardadas de un jugador (cualquier campeón y posición)."""
        with self._lock:
            return [i for (i,) in self._db.execute("SELECT DISTINCT id FROM reg WHERE puuid=?", (puuid,)).fetchall()]

    def niveles(self):
        """{puuid: 'CHALLENGER' | 'GRANDMASTER' | 'MASTER'} de las ligas que ha mirado el recolector."""
        with self._lock:
            filas = self._db.execute("SELECT valor FROM kv WHERE clave LIKE 'ligas:%'").fetchall()
        out = {}
        for (valor,) in filas:
            out.update(json.loads(valor))
        return out

    def de(self, puuids, a, pos):
        """Tus registros con ese campeón en esa posición, contra cualquiera."""
        puuids = list(puuids)
        if not puuids:
            return []
        marcas = ",".join("?" * len(puuids))
        filtro, args = ("AND pos=?", (pos,)) if pos else ("", ())
        with self._lock:
            filas = self._db.execute(
                f"SELECT datos FROM reg WHERE puuid IN ({marcas}) AND a=? {filtro}", (*puuids, a, *args)
            ).fetchall()
        return [desempaquetar(d) for (d,) in filas]

    def cuantos(self, a, pos):
        """Partidas guardadas de ese campeón en esa posición, por rival."""
        with self._lock:
            return dict(self._db.execute("SELECT b, COUNT(*) FROM reg WHERE a=? AND pos=? GROUP BY b", (a, pos)).fetchall())

    def resumen(self):
        with self._lock:
            partidas = self._db.execute("SELECT COUNT(*) FROM vista WHERE util=1").fetchone()[0]
            miradas = self._db.execute("SELECT COUNT(*) FROM vista").fetchone()[0]
        return {"partidas": partidas, "miradas": miradas}
