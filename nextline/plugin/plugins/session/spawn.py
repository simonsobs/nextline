import asyncio
import multiprocessing as mp
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from logging import getLogger
from typing import cast

from tblib import pickling_support

from nextline import spawned
from nextline.plugin.spec import Context
from nextline.spawned import Command, QueueIn, QueueOut, RunResult
from nextline.utils import RunningProcess, run_in_process

pickling_support.install()


@asynccontextmanager
async def run_session(
    context: Context,
) -> AsyncIterator[tuple[RunningProcess[RunResult], Callable[[Command], None]]]:
    assert context.run_arg
    mp_context = mp.get_context('spawn')
    queue_in = cast(QueueIn, mp_context.Queue())
    queue_out = cast(QueueOut, mp_context.Queue())
    send_command = SendCommand(queue_in)
    func = partial(spawned.main, context.run_arg)
    async with relay_events(context, queue_out):
        running = await run_in_process(
            func,
            mp_context=mp_context,
            initializer=partial(spawned.set_queues, queue_in, queue_out),
            collect_logging=True,
        )
        yield running, send_command


def SendCommand(queue_in: QueueIn) -> Callable[[Command], None]:
    def _send_command(command: Command) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}')
        queue_in.put(command)

    return _send_command


@asynccontextmanager
async def relay_events(context: Context, queue: QueueOut) -> AsyncIterator[None]:
    '''Call the hook `on_event_in_process()` on events emitted in the spawned process.'''
    logger = getLogger(__name__)

    async def _monitor() -> None:
        while (event := await asyncio.to_thread(queue.get)) is not None:
            logger.debug(f'event: {event!r}')
            await context.hook.ahook.on_event_in_process(context=context, event=event)

    task = asyncio.create_task(_monitor())
    try:
        yield
    finally:
        up_to = 0.05
        start = time.process_time()
        while not queue.empty():
            await asyncio.sleep(0)
            if time.process_time() - start > up_to:
                logger.warning(f'Timeout. the queue is not empty: {queue!r}')
                break
        await asyncio.to_thread(queue.put, None)  # type: ignore
        await task
