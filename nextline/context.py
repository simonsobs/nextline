from __future__ import annotations

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from logging import getLogger
from typing import Any, AsyncIterator, Callable, Optional, Tuple

from apluggy import PluginManager, asynccontextmanager
from tblib import pickling_support

from . import spawned
from .count import RunNoCounter
from .hook import build_hook
from .monitor import Monitor
from .spawned import QueueCommands, QueueOut, RunArg, RunResult
from .types import PromptNo, RunNo, TraceNo
from .utils import MultiprocessingLogging, PubSub, Result, Running, run_in_process

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


def _call_all(*funcs) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


class Resource:
    def __init__(self, hook: PluginManager) -> None:
        self._hook = hook
        self._mp_context = mp.get_context('spawn')

    @asynccontextmanager
    async def run(
        self, run_arg: RunArg
    ) -> AsyncIterator[Tuple[Running[RunResult], Callable[[str, int, int], None]]]:
        queue_out: QueueOut = self._mp_context.Queue()
        monitor = Monitor(self._hook, queue_out)
        async with MultiprocessingLogging(mp_context=self._mp_context) as mp_logging:
            async with monitor:
                q_commands = self._mp_context.Queue()
                initializer = partial(
                    _call_all,
                    mp_logging.initializer,
                    partial(spawned.set_queues, q_commands, queue_out),
                )
                executor_factory = partial(
                    ProcessPoolExecutor,
                    max_workers=1,
                    mp_context=self._mp_context,
                    initializer=initializer,
                )
                func = partial(spawned.main, run_arg)
                running = await run_in_process(func, executor_factory)
                send_pdb_command = SendPdbCommand(q_commands)
                yield running, send_pdb_command


def SendPdbCommand(q_commands: QueueCommands) -> Callable[[str, int, int], None]:
    def _send_pdb_command(command: str, prompt_no: int, trace_no: int) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}, {prompt_no!r}, {trace_no!r})')
        q_commands.put((command, PromptNo(prompt_no), TraceNo(trace_no)))

    return _send_pdb_command


class Context:
    def __init__(self, run_no_start_from: int, statement: str):
        self._hook = build_hook()
        self._resource = Resource(hook=self._hook)
        self.registry = PubSub[Any, Any]()
        self._hook.hook.init(hook=self._hook, registry=self.registry)
        self._run_no_count = RunNoCounter(run_no_start_from)
        self._running: Optional[Running[RunResult]] = None
        self._send_pdb_command: Optional[Callable[[str, int, int], None]] = None
        self._run_arg = RunArg(
            run_no=RunNo(run_no_start_from - 1),
            statement=statement,
            filename=SCRIPT_FILE_NAME,
        )
        self._run_result: RunResult | None = None

    async def start(self) -> None:
        await self._hook.ahook.start()
        await self._hook.ahook.on_change_script(
            script=self._run_arg['statement'], filename=self._run_arg['filename']
        )

    async def state_change(self, state_name: str):
        await self._hook.ahook.on_change_state(state_name=state_name)

    async def shutdown(self) -> None:
        await self.registry.close()
        await self._hook.ahook.close()

    async def initialize(self) -> None:
        self._run_arg['run_no'] = self._run_no_count()
        self._run_result = None
        await self._hook.ahook.on_initialize_run(run_no=self._run_arg['run_no'])

    async def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        if statement:
            self._run_arg['statement'] = statement
            await self._hook.ahook.on_change_script(
                script=statement, filename=self._run_arg['filename']
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        try:
            async with self._resource.run(self._run_arg) as (running, send_pdb_command):
                self._running = running
                self._send_pdb_command = send_pdb_command
                await self._hook.ahook.on_start_run()
                yield
                ret = await running
                self._running = None
                self._send_pdb_command = None
        finally:
            await self._finish(ret)

    async def _finish(self, ret: Result[RunResult]) -> None:
        self._run_result = ret.returned or RunResult(ret=None, exc=None)
        if ret.raised:
            logger = getLogger(__name__)
            logger.exception(ret.raised)
        await self._hook.ahook.on_end_run(run_result=self._run_result)

    def send_pdb_command(self, command: str, prompt_no: int, trace_no: int) -> None:
        if self._send_pdb_command:
            self._send_pdb_command(command, prompt_no, trace_no)

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
