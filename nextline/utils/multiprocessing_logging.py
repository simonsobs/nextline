from __future__ import annotations

from queue import Queue  # noqa F401

from multiprocessing.context import BaseContext
from concurrent.futures import ThreadPoolExecutor
import logging
from logging.handlers import QueueHandler
from typing_extensions import TypeAlias


QueueLogging: TypeAlias = "Queue[logging.LogRecord]"


class MultiprocessingLogging:
    def __init__(self, context: BaseContext):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._q: QueueLogging = context.Queue()
        self._fut = self._executor.submit(logger_thread, self._q)
        self._init = ConfigureLogger(self._q)

    @property
    def init(self):
        return self._init

    def close(self) -> None:
        self._q.put(None)  # type: ignore
        self._fut.result()
        self._executor.shutdown()


class ConfigureLogger:
    def __init__(self, queue: QueueLogging):
        self._queue = queue

    def __call__(self):
        handler = QueueHandler(self._queue)
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)


def logger_thread(queue: QueueLogging):
    # https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
    # https://github.com/alphatwirl/mantichora/blob/v0.12.0/mantichora/hubmp.py
    while (record := queue.get()) is not None:
        logger = logging.getLogger(record.name)
        if logger.getEffectiveLevel() <= record.levelno:
            logger.handle(record)
