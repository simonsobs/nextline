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
from .utils import (
    ExitedProcess,
    MultiprocessingLogging,
    PubSub,
    RunningProcess,
    run_in_process,
)

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
        self._run_arg = RunArg(
            run_no=RunNo(run_no_start_from - 1),
            statement=statement,
            filename=SCRIPT_FILE_NAME,
        )

    async def start(self) -> None:
        await self._hook.ahook.start()
        await self._hook.ahook.on_change_script(
            script=self._run_arg.statement, filename=self._run_arg.filename
        )

    async def state_change(self, state_name: str):
        await self._hook.ahook.on_change_state(state_name=state_name)

    async def close(self):
        await self.registry.close()
        await self._hook.ahook.close()

    async def initialize(self) -> None:
        self._run_arg.run_no = self._run_no_count()
        await self._hook.ahook.on_initialize_run(run_arg=self._run_arg)

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
    async def run(
        self,
    ) -> AsyncIterator[Tuple[RunningProcess[RunResult], Callable[[Command], None]]]:
        try:
            con = run_with_resource(self._hook, self._run_arg)
            async with con as (running, send_command):
                await self._hook.ahook.on_start_run()
                exited = yield running, send_command
                yield  # type: ignore
        finally:
            await self._finish(exited)  # type: ignore

    async def _finish(self, exited: ExitedProcess[RunResult]) -> None:
        run_result = exited.returned or RunResult(ret=None, exc=None)
        if exited.raised:
            logger = getLogger(__name__)
            logger.exception(exited.raised)
        await self._hook.ahook.on_end_run(run_result=run_result)
