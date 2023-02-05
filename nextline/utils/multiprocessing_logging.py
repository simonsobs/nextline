from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
from functools import partial
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
    '''Collect logging from other processes in the main process.

    Example:

    >>> async def main():
    ...     from concurrent.futures import ProcessPoolExecutor
    ...     async with MultiprocessingLogging() as mp_logging:
    ...         with ProcessPoolExecutor(initializer=mp_logging.initializer) as executor:
    ...             future = executor.submit(example_func)
    ...             future.result()

    >>> asyncio.run(main())

    Reference:
    "Logging to a single file from multiple processes" (Logging Cookbook)
    https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes

    '''

    def __init__(self, mp_context: Optional[BaseContext] = None) -> None:
        mp_context = mp_context or mp.get_context()
        self._q: Queue[LogRecord | None] = mp_context.Queue()
        self._initializer = partial(_initializer, self._q)
        self._task: asyncio.Task | None = None

    @property
    def initializer(self) -> Callable[[], None]:
        '''A callable with no args to be given to ProcessPoolExecutor as initializer.'''
        return self._initializer

    async def open(self):
        self._task = asyncio.create_task(_listen(self._q))

    async def close(self) -> None:
        if self._task:
            await to_thread(self._q.put, None)
            await self._task
            self._task = None

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        del exc_type, exc_value, traceback
        await self.close()


def _initializer(queue: Queue[LogRecord]) -> None:
    '''An initializer of ProcessPoolExecutor.'''
    handler = QueueHandler(queue)
    logger = getLogger()
    logger.setLevel(DEBUG)
    logger.addHandler(handler)


async def _listen(queue: Queue[LogRecord | None]) -> None:
    '''Receive loggings from other processes and handle them in the main process.'''
    while (record := await to_thread(queue.get)) is not None:
        logger = getLogger(record.name)
        if logger.getEffectiveLevel() <= record.levelno:
            logger.handle(record)
