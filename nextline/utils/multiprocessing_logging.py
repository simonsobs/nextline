import asyncio
import contextlib
import logging
import multiprocessing as mp
from functools import partial
from logging import DEBUG, LogRecord, getLogger
from logging.handlers import QueueHandler
from multiprocessing.context import BaseContext
from queue import Queue
from typing import Optional, cast

__all__ = ['MultiprocessingLogging']


def example_func() -> None:
    '''Used in doctest, defined here to be picklable.'''
    logger = logging.getLogger(__name__)
    logger.warning('warning from another process')


@contextlib.asynccontextmanager
async def MultiprocessingLogging(mp_context: Optional[BaseContext] = None):
    '''Collect logging from other processes in the main process.

    Example:

    A function to be executed in another process is example_func(), which is defined
    outside of the docstring because it must be picklable.

    Define the main asynchronous function, in which MultiprocessingLogging is used.

    >>> async def main():
    ...     from concurrent.futures import ProcessPoolExecutor
    ...
    ...     # Start MultiprocessingLogging.
    ...     async with MultiprocessingLogging() as initializer:
    ...
    ...         # The initializer is given to ProcessPoolExecutor.
    ...         with ProcessPoolExecutor(initializer=initializer) as executor:
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

    mp_context = mp_context or mp.get_context()
    queue = cast(Queue[LogRecord | None], mp_context.Queue())
    initializer = partial(_initializer, queue)

    async def _listen() -> None:
        '''Receive loggings from other processes and handle them in the current process.'''
        while (record := await asyncio.to_thread(queue.get)) is not None:
            logger = getLogger(record.name)
            if logger.getEffectiveLevel() <= record.levelno:
                logger.handle(record)

    task = asyncio.create_task(_listen())

    try:
        yield initializer
    finally:
        await asyncio.to_thread(queue.put, None)
        await task


def _initializer(queue: Queue[LogRecord]) -> None:
    '''An initializer of ProcessPoolExecutor.'''
    handler = QueueHandler(queue)
    logger = getLogger()
    logger.setLevel(DEBUG)
    logger.addHandler(handler)
