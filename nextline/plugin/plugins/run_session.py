import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from logging import getLogger
from typing import Any, AsyncIterator, Callable, Optional, Tuple

import apluggy
from tblib import pickling_support

from nextline import spawned
from nextline.monitor import Monitor
from nextline.plugin.spec import hookimpl
from nextline.spawned import Command, QueueIn, QueueOut, RunArg, RunResult
from nextline.utils import MultiprocessingLogging, RunningProcess, run_in_process

pickling_support.install()


class RunSession:
    @hookimpl
    def init(self, hook: apluggy.PluginManager) -> None:
        self._hook = hook

    @hookimpl
    async def on_initialize_run(self, run_arg: RunArg) -> None:
        self._run_arg = run_arg

    @hookimpl
    @apluggy.asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        con = run_with_resource(self._hook, self._run_arg)
        async with con as (running, send_command):
            await self._hook.ahook.on_start_run()
            self._running = running
            self._send_command = send_command
            yield
            exited = await running
        if exited.raised:
            logger = getLogger(__name__)
            logger.exception(exited.raised)
        self._run_result = exited.returned or RunResult(ret=None, exc=None)
        await self._hook.ahook.on_end_run(run_result=self._run_result)

    @hookimpl
    async def send_command(self, command: Command) -> None:
        self._send_command(command)

    @hookimpl
    async def interrupt(self) -> None:
        self._running.interrupt()

    @hookimpl
    async def terminate(self) -> None:
        self._running.terminate()

    @hookimpl
    async def kill(self) -> None:
        self._running.kill()

    @hookimpl
    def exception(self) -> Optional[BaseException]:
        return self._run_result.exc

    @hookimpl
    def result(self) -> Any:
        return self._run_result.result()


def _call_all(*funcs) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


@asynccontextmanager
async def run_with_resource(
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
