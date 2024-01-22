import multiprocessing as mp
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from logging import getLogger
from typing import cast

from tblib import pickling_support

from nextline import spawned
from nextline.plugin.spec import Context
from nextline.spawned import Command, QueueIn, QueueOut, RunResult
from nextline.utils import MultiprocessingLogging, RunningProcess, run_in_process

from .monitor import relay_queue

pickling_support.install()


def _call_all(*funcs: Callable) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


@asynccontextmanager
async def run_session(
    context: Context,
) -> AsyncIterator[tuple[RunningProcess[RunResult], Callable[[Command], None]]]:
    assert context.run_arg
    mp_context = mp.get_context('spawn')
    queue_in = cast(QueueIn, mp_context.Queue())
    queue_out = cast(QueueOut, mp_context.Queue())
    send_command = SendCommand(queue_in)
    async with MultiprocessingLogging(mp_context=mp_context) as mp_logging:
        initializer = partial(
            _call_all,
            mp_logging.initializer,
            partial(spawned.set_queues, queue_in, queue_out),
        )
        func = partial(spawned.main, context.run_arg)
        async with relay_queue(context, queue_out):
            running = await run_in_process(
                func,
                mp_context=mp_context,
                initializer=initializer,
            )
            yield running, send_command


def SendCommand(queue_in: QueueIn) -> Callable[[Command], None]:
    def _send_command(command: Command) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}')
        queue_in.put(command)

    return _send_command
