import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from logging import getLogger
from typing import AsyncIterator, Callable, Tuple

import apluggy
from tblib import pickling_support

from nextline import spawned
from nextline.spawned import Command, QueueIn, QueueOut, RunArg, RunResult
from nextline.utils import MultiprocessingLogging, RunningProcess, run_in_process

from .monitor import Monitor

pickling_support.install()


def _call_all(*funcs) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


@asynccontextmanager
async def run_session(
    hook: apluggy.PluginManager, run_arg: RunArg
) -> AsyncIterator[Tuple[RunningProcess[RunResult], Callable[[Command], None]]]:
    mp_context = mp.get_context('spawn')
    queue_in: QueueIn = mp_context.Queue()
    queue_out: QueueOut = mp_context.Queue()
    send_command = SendCommand(queue_in)
    monitor = Monitor(hook, queue_out)
    async with MultiprocessingLogging(mp_context=mp_context) as mp_logging:
        initializer = partial(
            _call_all,
            mp_logging.initializer,
            partial(spawned.set_queues, queue_in, queue_out),
        )
        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=mp_context,
            initializer=initializer,
        )
        func = partial(spawned.main, run_arg)
        async with monitor:
            running = await run_in_process(func, executor_factory)
            yield running, send_command


def SendCommand(queue_in: QueueIn) -> Callable[[Command], None]:
    def _send_command(command: Command) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}')
        queue_in.put(command)

    return _send_command
