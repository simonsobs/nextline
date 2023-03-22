from __future__ import annotations

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from logging import getLogger
from pathlib import Path
from types import CodeType
from typing import Any, AsyncIterator, Callable, Optional, Tuple, Union

from apluggy import PluginManager
from tblib import pickling_support

from . import spawned
from .count import RunNoCounter
from .monitor import Monitor
from .plugin import build_hook
from .spawned import Command, QueueIn, QueueOut, RunArg, RunResult
from .types import RunNo
from .utils import MultiprocessingLogging, PubSub, Result, Running, run_in_process

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


def _call_all(*funcs) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


@asynccontextmanager
async def run_with_resource(
    hook: PluginManager, run_arg: RunArg
) -> AsyncIterator[Tuple[Running[RunResult], Callable[[Command], None]]]:
    mp_context = mp.get_context('spawn')
    queue_in: QueueIn = mp_context.Queue()
    queue_out: QueueOut = mp_context.Queue()
    monitor = Monitor(hook, queue_out)
    async with MultiprocessingLogging(mp_context=mp_context) as mp_logging:
        async with monitor:
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
            running = await run_in_process(func, executor_factory)
            send_command = SendCommand(queue_in)
            yield running, send_command


def SendCommand(queue_in: QueueIn) -> Callable[[Command], None]:
    def _send_command(command: Command) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}')
        queue_in.put(command)

    return _send_command


class Context:
    def __init__(
        self,
        run_no_start_from: int,
        statement: Union[str, Path, CodeType, Callable[[], Any]],
    ):
        self._hook = build_hook()
        self.registry = PubSub[Any, Any]()
        self._hook.hook.init(hook=self._hook, registry=self.registry)
        self._run_no_count = RunNoCounter(run_no_start_from)
        self._running: Optional[Running[RunResult]] = None
        self._send_command: Optional[Callable[[Command], None]] = None
        self._run_arg = RunArg(
            run_no=RunNo(run_no_start_from - 1),
            statement=statement,
            filename=SCRIPT_FILE_NAME,
        )
        self._run_result: RunResult | None = None

    async def start(self) -> None:
        await self._hook.ahook.start()
        await self._hook.ahook.on_change_script(
            script=self._run_arg.statement, filename=self._run_arg.filename
        )

    async def state_change(self, state_name: str):
        await self._hook.ahook.on_change_state(state_name=state_name)

    async def shutdown(self) -> None:
        await self.registry.close()
        await self._hook.ahook.close()

    async def initialize(self) -> None:
        self._run_arg.run_no = self._run_no_count()
        self._run_result = None
        await self._hook.ahook.on_initialize_run(run_no=self._run_arg.run_no)

    async def reset(
        self,
        statement: Union[str, Path, CodeType, Callable[[], Any], None],
        run_no_start_from: Optional[int] = None,
    ):
        if statement is not None:
            self._run_arg.statement = statement
            await self._hook.ahook.on_change_script(
                script=statement, filename=self._run_arg.filename
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        try:
            async with run_with_resource(self._hook, self._run_arg) as (
                running,
                send_command,
            ):
                self._running = running
                self._send_command = send_command
                await self._hook.ahook.on_start_run()
                yield
                ret = await running
                self._running = None
                self._send_command = None
        finally:
            await self._finish(ret)

    async def _finish(self, ret: Result[RunResult]) -> None:
        self._run_result = ret.returned or RunResult(ret=None, exc=None)
        if ret.raised:
            logger = getLogger(__name__)
            logger.exception(ret.raised)
        await self._hook.ahook.on_end_run(run_result=self._run_result)

    def send_command(self, command: Command) -> None:
        if self._send_command:
            self._send_command(command)

    def interrupt(self) -> None:
        if self._running:
            self._running.interrupt()

    def terminate(self) -> None:
        if self._running:
            self._running.terminate()

    def kill(self) -> None:
        if self._running:
            self._running.kill()

    def result(self) -> Any:
        assert self._run_result
        return self._run_result.result()

    def exception(self) -> Optional[BaseException]:
        assert self._run_result
        return self._run_result.exc

    async def close(self):
        pass
