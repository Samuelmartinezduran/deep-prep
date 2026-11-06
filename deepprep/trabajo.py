"""Cola de tareas con prioridad: lo que más informa (el jungla rival) se pide antes."""
import itertools
import queue
import threading
import traceback


class Cola:
    def __init__(self, hilos=6, al_fallar=None):
        self._q = queue.PriorityQueue()
        self._orden = itertools.count()
        self._al_fallar = al_fallar
        for i in range(hilos):
            threading.Thread(target=self._bucle, name=f"trabajo-{i}", daemon=True).start()

    def poner(self, prioridad, fn, *args):
        self._q.put((prioridad, next(self._orden), fn, args))

    def _bucle(self):
        while True:
            _, _, fn, args = self._q.get()
            try:
                fn(*args)
            except Exception as e:  # una tarea rota no debe tumbar el hilo
                if self._al_fallar:
                    self._al_fallar(e)
                else:
                    traceback.print_exc()
