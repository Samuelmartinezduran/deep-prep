"""Caché: en memoria solo se quedan las últimas partidas y líneas usadas; las demás siguen en la base."""

import threading
import unittest
from unittest import mock

from deepprep import cache as cache_mod
from deepprep.cache import Cache


def partida(i):
    return {"id": f"EUW1_{i}", "creacion": 1_000 + i, "cola": 420, "jug": [{"puuid": "yo"}, {"puuid": f"otro{i}"}]}


class EnMemoria(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(cache_mod, "MAX_PARTIDAS", 3), mock.patch.object(cache_mod, "MAX_LINEAS", 2)):
            self.enterContext(p)
        self.cache = Cache(":memory:")
        self.addCleanup(self.cache.cerrar)

    def test_se_queda_con_las_ultimas_y_las_demas_siguen_en_la_base(self):
        for i in range(10):
            self.cache.guardar_partida(partida(i))
        self.assertEqual(len(self.cache._partidas), 3)
        self.assertEqual(self.cache.partida("EUW1_0"), partida(0))  # fuera de la memoria, pero en la base
        self.assertEqual(len(self.cache._partidas), 3)
        self.assertEqual([p["id"] for p in self.cache.partidas_de("yo")], [f"EUW1_{i}" for i in range(9, -1, -1)])
        self.assertEqual(len(self.cache._partidas), 3)

    def test_la_que_se_usa_no_se_va(self):
        for i in range(3):
            self.cache.guardar_partida(partida(i))
        self.cache.partida("EUW1_0")  # la más vieja pasa a ser la más reciente
        self.cache.guardar_partida(partida(3))
        self.assertEqual(list(self.cache._partidas._datos), ["EUW1_2", "EUW1_0", "EUW1_3"])

    def test_lineas_de_tiempo(self):
        for i in range(5):
            self.cache.guardar_linea({"id": f"EUW1_{i}", "pos": {}})
        self.assertEqual(len(self.cache._lineas), 2)
        self.assertEqual(self.cache.linea("EUW1_0"), {"id": "EUW1_0", "pos": {}})
        self.assertIsNone(self.cache.linea("no-existe"))
        self.assertEqual(len(self.cache._lineas), 2)

    def test_vaciar(self):
        self.cache.guardar_partida(partida(1))
        self.cache.guardar_linea({"id": "EUW1_1"})
        self.cache.vaciar()
        self.assertEqual((len(self.cache._partidas), len(self.cache._lineas)), (0, 0))
        self.assertIsNone(self.cache.partida("EUW1_1"))

    def test_desde_varios_hilos(self):
        errores = []

        def usar(n):
            try:
                for i in range(200):
                    self.cache.guardar_partida(partida(n * 1000 + i))
                    self.cache.partida(f"EUW1_{n * 1000 + i // 2}")
            except Exception as e:  # noqa: BLE001  cualquier fallo de un hilo tiene que llegar a la prueba
                errores.append(e)

        hilos = [threading.Thread(target=usar, args=(n,)) for n in range(4)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(len(self.cache._partidas), 3)
        self.assertEqual(len(self.cache.partidas_de("yo")), 800)


if __name__ == "__main__":
    unittest.main()
