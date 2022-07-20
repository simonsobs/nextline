from __future__ import annotations

from dataclasses import dataclass, InitVar, field
from functools import partial
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import traceback
from typing import TYPE_CHECKING, Callable, Coroutine, Optional, Any
from typing_extensions import ParamSpec

from .utils import (
    PubSub,
    MultiprocessingLogging,
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

_P = ParamSpec("_P")


def _initializer(
    init_logging: Callable[[], Any],
    initializer: Callable[_P, Any],
    *initargs: _P.args,
    **initkwargs: _P.kwargs,
) -> None:
    init_logging()
    if initializer is not None:
        initializer(*initargs, **initkwargs)


@dataclass
class Context:
    run_no_start_from: InitVar[int]
    statement: str
    filename: str = SCRIPT_FILE_NAME
    func: Callable = run.run
    state: Optional[State] = None
    future: Optional[RunInProcess] = None
    result: Optional[Any] = None
    exception: Optional[BaseException] = None
    registry: PubSub[Any, Any] = field(init=False)
    q_commands: QueueCommands = field(init=False)
    registrar: Registrar = field(init=False)
    run_no: RunNo = field(init=False)
    run_no_count: Callable[[], RunNo] = field(init=False)
    mp_logging: MultiprocessingLogging = field(init=False)
    runner: Callable[
        ...,
        Coroutine[Any, Any, RunInProcess],
    ] = field(init=False)

    def __post_init__(self, run_no_start_from: int):
        self.registry = PubSub[Any, Any]()
        mp_context = mp.get_context("spawn")
        self.q_commands: QueueCommands = mp_context.Queue()
        q_registry: QueueRegistry = mp_context.Queue()
        self.mp_logging = MultiprocessingLogging(context=mp_context)
        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=mp_context,
            initializer=partial(
                _initializer,
                self.mp_logging.init,
                run.set_queues,
            ),
            initargs=(self.q_commands, q_registry),
        )
        self.runner = partial(run_in_process, executor_factory)  # type: ignore
        self.registrar = Registrar(self.registry, q_registry)
        self.run_no = RunNo(run_no_start_from - 1)
        self.run_no_count = RunNoCounter(run_no_start_from)

    async def start(self):
        await self.registrar.script_change(
            script=self.statement, filename=self.filename
        )

    async def shutdown(self):
        await self.registrar.close()
        await self.mp_logging.close()

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
