import asyncio
import contextlib
import multiprocessing as mp
import time
from collections.abc import AsyncIterator, Callable
from functools import partial
from logging import getLogger
from typing import Any, Optional, cast

import apluggy
from tblib import pickling_support

from nextline import spawned
from nextline.plugin.spec import Context, hookimpl
from nextline.spawned import Command, QueueIn, QueueOut, RunResult
from nextline.utils import run_in_process

pickling_support.install()


class RunSession:
    @hookimpl
    @apluggy.asynccontextmanager
    async def run(self, context: Context) -> AsyncIterator[None]:
        assert context.run_arg
        context.exited_process = None
        mp_context = mp.get_context('spawn')
        queue_in = cast(QueueIn, mp_context.Queue())
        queue_out = cast(QueueOut, mp_context.Queue())
        context.send_command = SendCommand(queue_in)
        async with relay_events(context, queue_out):
            context.running_process = await run_in_process(
                func=partial(spawned.main, context.run_arg),
                mp_context=mp_context,
                initializer=partial(spawned.set_queues, queue_in, queue_out),
                collect_logging=True,
            )
            await context.hook.ahook.on_start_run(context=context)
            try:
                yield
            finally:
                context.exited_process = await context.running_process
                context.running_process = None
                if context.exited_process.raised:
                    logger = getLogger(__name__)
                    logger.exception(context.exited_process.raised)
                await context.hook.ahook.on_end_run(context=context)


def SendCommand(queue_in: QueueIn) -> Callable[[Command], None]:
    def _send_command(command: Command) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}')
        queue_in.put(command)

    return _send_command


@contextlib.asynccontextmanager
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


class Signal:
    @hookimpl
    async def interrupt(self, context: Context) -> None:
        assert context.running_process
        context.running_process.interrupt()

    @hookimpl
    async def terminate(self, context: Context) -> None:
        assert context.running_process
        context.running_process.terminate()

    @hookimpl
    async def kill(self, context: Context) -> None:
        assert context.running_process
        context.running_process.kill()


class CommandSender:
    @hookimpl
    async def send_command(self, context: Context, command: Command) -> None:
        assert context.send_command
        context.send_command(command)


class Result:
    @hookimpl
    async def on_end_run(self, context: Context) -> None:
        assert context.exited_process
        self._run_result = context.exited_process.returned or RunResult()

    @hookimpl
    def exception(self) -> Optional[BaseException]:
        return self._run_result.exc

    @hookimpl
    def result(self) -> Any:
        return self._run_result.result()
