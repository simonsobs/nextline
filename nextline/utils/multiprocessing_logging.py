'''Collect logging from other processes in the main process.

The original implementation was based on code in logging cookbook:
https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes


Example:

>>> async def main():
...     from concurrent.futures import ProcessPoolExecutor
...     async with MultiprocessingLogging() as mp_logging:
...         with ProcessPoolExecutor(initializer=mp_logging.init) as executor:
...             future = executor.submit(example_func)
...             future.result()

>>> asyncio.run(main())

'''

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
from logging import DEBUG, LogRecord, getLogger
from logging.handlers import QueueHandler
from multiprocessing.context import BaseContext
from queue import Queue
from typing import Callable, Optional

from .func import to_thread

__all__ = ['MultiprocessingLogging']


def example_func():
    '''Used in doctest, defined here to be picklable.'''
    logger = logging.getLogger(__name__)
    logger.warning('foo')


class MultiprocessingLogging:
    def __init__(self, context: Optional[BaseContext] = None) -> None:
        context = context or mp.get_context()
        self._q: Queue[LogRecord | None] = context.Queue()
        self._init = _ConfigureLogger(self._q)

    @property
    def init(self) -> Callable[[], None]:
        '''A (picklable) setup function to be called in other processes'''
        return self._init

    async def open(self):
        self._task = asyncio.create_task(_listen(self._q))

    async def close(self) -> None:
        await to_thread(self._q.put, None)
        await self._task

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        del exc_type, exc_value, traceback
        await self.close()


class _ConfigureLogger:
    def __init__(self, queue: Queue[LogRecord]):
        self._queue = queue

    def __call__(self) -> None:
        handler = QueueHandler(self._queue)
        logger = getLogger()
        logger.setLevel(DEBUG)
        logger.addHandler(handler)


async def _listen(queue: Queue[LogRecord | None]) -> None:
    while (record := await to_thread(queue.get)) is not None:
        logger = getLogger(record.name)
        if logger.getEffectiveLevel() <= record.levelno:
            logger.handle(record)
