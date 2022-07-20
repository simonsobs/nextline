"""Handle logging in a multiprocessing environment.

https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
https://github.com/alphatwirl/mantichora/blob/v0.12.0/mantichora/hubmp.py

"""

from __future__ import annotations

from functools import partial
from queue import Queue  # noqa F401

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import multiprocessing as mp
from multiprocessing.context import BaseContext

from logging import LogRecord, getLogger, DEBUG
from logging.handlers import QueueHandler
from typing import Callable, Optional

__all__ = ["ProcessPoolExecutorWithLoggingA", "MultiprocessingLoggingA"]


def _initializer(init_logging, initializer, *initargs):
    init_logging()
    if initializer is not None:
        initializer(*initargs)


class ProcessPoolExecutorWithLoggingA(ProcessPoolExecutor):
    def __init__(
        self, max_workers=None, mp_context=None, initializer=None, initargs=()
    ):
        self._mp_logging = MultiprocessingLoggingA(context=mp_context)
        initializer = partial(_initializer, self._mp_logging.init, initializer)
        super().__init__(max_workers, mp_context, initializer, initargs)

    def shutdown(self, wait=True):
        self._mp_logging.close()
        super().shutdown(wait)


class MultiprocessingLoggingA:
    def __init__(self, context: Optional[BaseContext] = None) -> None:
        context = context or mp.get_context()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._q: Queue[LogRecord | None] = context.Queue()
        self._fut = self._executor.submit(_listen, self._q)
        self._init = _ConfigureLogger(self._q)

    @property
    def init(self) -> Callable[[], None]:
        """A (picklable) setup function to be called in other processes"""
        return self._init

    def close(self) -> None:
        self._q.put(None)
        self._fut.result()
        self._executor.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        del exc_type, exc_value, traceback
        self.close()


class _ConfigureLogger:
    def __init__(self, queue: Queue[LogRecord]):
        self._queue = queue

    def __call__(self) -> None:
        handler = QueueHandler(self._queue)
        logger = getLogger()
        logger.setLevel(DEBUG)
        logger.addHandler(handler)


def _listen(queue: Queue[LogRecord | None]) -> None:
    while (record := queue.get()) is not None:
        logger = getLogger(record.name)
        if logger.getEffectiveLevel() <= record.levelno:
            logger.handle(record)
