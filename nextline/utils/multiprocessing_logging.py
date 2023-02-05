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
    logger.warning('warning from another process')


class MultiprocessingLogging:
    '''Collect logging from other processes in the main process.

    Example:

    A function to be executed in another process is example_func(), which is defined
    outside of the docstring because it must be picklable.

    Define the main asynchronous function, in which MultiprocessingLogging is used.

    >>> async def main():
    ...     from concurrent.futures import ProcessPoolExecutor
    ...
    ...     # Start MultiprocessingLogging.
    ...     async with MultiprocessingLogging() as mp_logging:
    ...
    ...         # The initializer is given to ProcessPoolExecutor.
    ...         with ProcessPoolExecutor(initializer=mp_logging.initializer) as executor:
    ...
    ...             # In another process, execute example_func(), which logs a warning.
    ...             future = executor.submit(example_func)
    ...
    ...             # Wait until the function returns.
    ...             future.result()

    When the main() is executed, the warning in example_func() is received in the
    main process.

    To confirm that it works in this example, we add a queue handler to the
    current logger.

    >>> queue = Queue()
    >>> handler = QueueHandler(queue)
    >>> logger = logging.getLogger(__name__)
    >>> logger.addHandler(handler)

    Run the main function.

    >>> asyncio.run(main())

    Check the loggings in the queue.

    >>> log_record = queue.get()
    >>> log_record.getMessage()
    'warning from another process'

    Remove the queue handler added for the example.

    >>> logger.removeHandler(handler)


    Reference: "Logging to a single file from multiple processes" (Logging Cookbook)
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
        self._task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        '''Receive loggings from other processes and handle them in the main process.'''
        while (record := await to_thread(self._q.get)) is not None:
            logger = getLogger(record.name)
            if logger.getEffectiveLevel() <= record.levelno:
                logger.handle(record)

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
