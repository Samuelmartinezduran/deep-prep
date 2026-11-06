"""Cola de tareas con prioridad: lo que más informa (el jungla rival) se pide antes."""

import itertools
import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class Cola:
    def __init__(self, hilos: int = 6, al_fallar: Callable[[Exception], None] | None = None) -> None:
        self._q: queue.PriorityQueue[tuple[int, int, Callable[..., object], tuple[Any, ...]]] = queue.PriorityQueue()
        self._orden = itertools.count()
        self._al_fallar = al_fallar
        for i in range(hilos):
            threading.Thread(target=self._bucle, name=f"trabajo-{i}", daemon=True).start()

    def poner(self, prioridad: int, fn: Callable[..., object], *args: Any) -> None:
        self._q.put((prioridad, next(self._orden), fn, args))

    def _bucle(self) -> None:
        while True:
            _, _, fn, args = self._q.get()
            try:
                fn(*args)
            except Exception as e:  # una tarea rota no debe tumbar el hilo
                if self._al_fallar:
                    self._al_fallar(e)
                else:
                    logger.exception("Tarea rota")
