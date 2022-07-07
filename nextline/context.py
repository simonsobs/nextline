from __future__ import annotations

from dataclasses import dataclass, InitVar, field
from functools import partial
import json
import multiprocessing as mp
import traceback
from typing import TYPE_CHECKING, Callable, Coroutine, Optional, Any

from .utils import (
    PubSub,
    ProcessPoolExecutorWithLogging,
    run_in_process,
    RunInProcess,
)
from .process import run
from .process.run import QueueRegistry, RunArg, QueueCommands
from .registrar import Registrar
from .types import RunNo
from .count import RunNoCounter

if TYPE_CHECKING:
    from .state import State

SCRIPT_FILE_NAME = "<string>"


@dataclass
class Context:
    statement: str
    filename: str
    runner: Callable[..., Coroutine[Any, Any, RunInProcess]]
    func: Callable
    registry: InitVar[PubSub[Any, Any]]
    q_registry: InitVar[QueueRegistry]
    run_no_start_from: InitVar[int]
    state: Optional[State] = None
    future: Optional[RunInProcess] = None
    result: Optional[Any] = None
    exception: Optional[BaseException] = None
    registrar: Registrar = field(init=False)
    run_no: RunNo = field(init=False)
    run_no_count: Callable[[], RunNo] = field(init=False)

    def __post_init__(
        self,
        registry: PubSub[Any, Any],
        q_registry: QueueRegistry,
        run_no_start_from: int,
    ):
        self.registrar = Registrar(registry, q_registry)
        self.run_no = RunNo(run_no_start_from - 1)
        self.run_no_count = RunNoCounter(run_no_start_from)

    async def start(self):
        await self.registrar.script_change(
            script=self.statement, filename=self.filename
        )

    async def shutdown(self):
        await self.registrar.close()

    async def initialize(self, state: State):
        self.run_no = self.run_no_count()
        self.result = None
        self.exception = None
        await self.registrar.state_initialized(self.run_no)
        await self.registrar.state_change(state)
        self.state = state

    async def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        if statement:
            self.statement = statement
            await self.registrar.script_change(
                script=statement, filename=self.filename
            )
        if run_no_start_from is not None:
            self.run_no_count = RunNoCounter(run_no_start_from)

    async def run(self, state: State) -> RunInProcess:
        self.future = await self.runner(
            self.func,
            RunArg(
                run_no=self.run_no,
                statement=self.statement,
                filename=self.filename,
            ),
        )
        await self.registrar.run_start(self.run_no)
        await self.registrar.state_change(state)
        self.state = state
        return self.future

    def interrupt(self) -> None:
        if self.future:
            self.future.interrupt()

    def terminate(self) -> None:
        if self.future:
            self.future.terminate()

    def kill(self) -> None:
        if self.future:
            self.future.kill()

    async def finish(self, state: State) -> None:
        assert self.future
        try:
            self.result, self.exception = await self.future
        except TypeError:
            # The process was terminated.
            pass

        if self.exception:
            ret = None
            fmt_exc = "".join(
                traceback.format_exception(
                    type(self.exception),
                    self.exception,
                    self.exception.__traceback__,
                )
            )
        else:
            ret = json.dumps(self.result)
            fmt_exc = None

        await self.registrar.run_end(result=ret, exception=fmt_exc)
        await self.registrar.state_change(state)
        self.state = state

    async def close(self, state: State):
        await self.registrar.state_change(state)
        self.state = state


async def build_context(
    registry: PubSub[Any, Any],
    q_commands: QueueCommands,
    mp_context: mp.context.BaseContext,
    statement: str,
    run_no_start_from=1,
):
    q_registry: QueueRegistry = mp_context.Queue()
    executor_factory = partial(
        ProcessPoolExecutorWithLogging,
        max_workers=1,
        mp_context=mp_context,
        initializer=run.set_queues,
        initargs=(q_commands, q_registry),
    )
    runner = partial(run_in_process, executor_factory)  # type: ignore
    filename = SCRIPT_FILE_NAME
    context = Context(
        registry=registry,
        q_registry=q_registry,
        run_no_start_from=run_no_start_from,
        statement=statement,
        filename=filename,
        runner=runner,
        func=run.run,
    )
    await context.start()
    return context
