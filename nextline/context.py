from __future__ import annotations

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from logging import getLogger
from typing import Any, Optional

from tblib import pickling_support

from . import process
from .count import RunNoCounter
from .process import QueueCommands, QueueRegistry, RunArg, RunResult
from .registrar import Registrar
from .types import PromptNo, RunNo, TraceNo
from .utils import MultiprocessingLogging, PubSub, Running, run_in_process

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


def _call_all(*funcs) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        func()


class Resource:
    def __init__(self) -> None:
        self.registry = PubSub[Any, Any]()
        self.q_commands: QueueCommands | None = None
        self._mp_context = mp.get_context('spawn')
        self._q_registry: QueueRegistry = self._mp_context.Queue()
        self._mp_logging = MultiprocessingLogging(mp_context=self._mp_context)
        self.registrar = Registrar(self.registry, self._q_registry)

    async def run(self, run_arg: RunArg) -> Running[RunResult]:
        func = partial(process.main, run_arg)
        self.q_commands = self._mp_context.Queue()
        initializer = partial(
            _call_all,
            self._mp_logging.initializer,
            partial(process.set_queues, self.q_commands, self._q_registry),
        )
        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=self._mp_context,
            initializer=initializer,
        )
        return await run_in_process(func, executor_factory)

    async def open(self):
        await self._mp_logging.open()
        await self.registrar.open()

    async def close(self):
        await self.registrar.close()
        await self._mp_logging.close()
        await self.registry.close()


class Context:
    def __init__(self, run_no_start_from: int, statement: str):
        self._resource = Resource()
        self.registry = self._resource.registry
        self._registrar = self._resource.registrar
        self._run_no_count = RunNoCounter(run_no_start_from)
        self._running: Optional[Running[RunResult]] = None
        self._run_arg = RunArg(
            run_no=RunNo(run_no_start_from - 1),
            statement=statement,
            filename=SCRIPT_FILE_NAME,
        )
        self._run_result: RunResult | None = None
        self._q_commands: QueueCommands | None = None

    async def start(self):
        await self._resource.open()
        await self._registrar.script_change(
            script=self._run_arg['statement'], filename=self._run_arg['filename']
        )

    async def state_change(self, state_name: str):
        await self._registrar.state_change(state_name)

    async def shutdown(self):
        await self._resource.close()

    async def initialize(self) -> None:
        self._run_arg['run_no'] = self._run_no_count()
        self._run_result = None
        await self._registrar.state_initialized(self._run_arg['run_no'])
        await self._registrar.run_initialized(self._run_arg['run_no'])

    async def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        if statement:
            self._run_arg['statement'] = statement
            await self._registrar.script_change(
                script=statement, filename=self._run_arg['filename']
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)

    async def run(self) -> Running:
        self._running = await self._resource.run(self._run_arg)
        self._q_commands = self._resource.q_commands
        assert self._q_commands
        await self._registrar.run_start()
        return self._running

    def send_pdb_command(self, command: str, prompt_no: int, trace_no: int) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}, {prompt_no!r}, {trace_no!r})')
        if self._q_commands:
            self._q_commands.put((command, PromptNo(prompt_no), TraceNo(trace_no)))

    def interrupt(self) -> None:
        if self._running:
            self._running.interrupt()

    def terminate(self) -> None:
        if self._running:
            self._running.terminate()

    def kill(self) -> None:
        if self._running:
            self._running.kill()

    async def finish(self) -> None:
        assert self._running
        ret = await self._running
        self._q_commands = None
        self._running = None

        self._run_result = ret.returned or RunResult(ret=None, exc=None)

        if ret.raised:
            logger = getLogger(__name__)
            logger.exception(ret.raised)

        await self._registrar.run_end(
            result=self._run_result.fmt_ret,
            exception=self._run_result.fmt_exc,
        )

    def result(self) -> Any:
        assert self._run_result
        return self._run_result.result()

    def exception(self) -> Optional[BaseException]:
        assert self._run_result
        return self._run_result.exc

    async def close(self):
        pass
