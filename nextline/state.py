from __future__ import annotations

from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

import os
import signal
import asyncio

from dataclasses import dataclass, InitVar, field
from functools import partial
import multiprocessing as mp
from tblib import pickling_support  # type: ignore
from typing import Callable, Coroutine, Generic, Optional, Any, Tuple, TypeVar
from typing_extensions import ParamSpec

from .utils import SubscribableDict, to_thread, ProcessPoolExecutorWithLogging
from .process import run
from .process.run import QueueRegistry, RunArg, QueueCommands
from .registrar import Registrar
from .types import PromptNo, RunNo, TraceNo
from .count import RunNoCounter

_mp = mp.get_context("spawn")  # NOTE: monkey patched in tests

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


_T = TypeVar("_T")
_P = ParamSpec("_P")


async def run_(
    executor_factory: Callable[[], Executor],
    func: Callable[_P, Tuple[_T | None, BaseException | None]],
    *func_args: _P.args,
    **func_kwargs: _P.kwargs,
) -> Run[_T, _P]:
    return await Run.create(executor_factory, func, *func_args, **func_kwargs)


class Run(Generic[_T, _P]):
    @classmethod
    async def create(
        cls,
        executor_factory: Callable[[], Executor],
        func: Callable[_P, Tuple[_T | None, BaseException | None]],
        *func_args: _P.args,
        **func_kwargs: _P.kwargs,
    ):
        self = cls(executor_factory, func, *func_args, **func_kwargs)
        assert await self._event.wait()
        return self

    def __init__(
        self,
        executor_factory: Callable[[], Executor],
        func: Callable[_P, Tuple[_T | None, BaseException | None]],
        *func_args: _P.args,
        **func_kwargs: _P.kwargs,
    ):
        self._executor_factory = executor_factory
        self._func_call = partial(func, *func_args, **func_kwargs)
        self._event = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> Tuple[Optional[_T], Optional[BaseException]]:

        with self._executor_factory() as executor:
            loop = asyncio.get_running_loop()
            f = loop.run_in_executor(executor, self._func_call)
            if isinstance(executor, ProcessPoolExecutor):
                self._process = list(executor._processes.values())[0]
            self._event.set()
            try:
                return await f
            except BrokenProcessPool:
                return None, None

    def interrupt(self) -> None:
        if self._process and self._process.pid:
            os.kill(self._process.pid, signal.SIGINT)

    def terminate(self) -> None:
        if self._process:
            self._process.terminate()

    def kill(self) -> None:
        if self._process:
            self._process.kill()

    def __await__(self):
        return self._task.__await__()


@dataclass
class Context:
    state: State
    statement: str
    filename: str
    runner: Callable[..., Coroutine[Any, Any, Run]]
    func: Callable
    registry: InitVar[SubscribableDict[Any, Any]]
    q_registry: InitVar[QueueRegistry]
    run_no_start_from: InitVar[int]
    registrar: Registrar = field(init=False)
    run_no: RunNo = field(init=False)
    run_no_count: Callable[[], RunNo] = field(init=False)

    def __post_init__(
        self,
        registry: SubscribableDict[Any, Any],
        q_registry: QueueRegistry,
        run_no_start_from: int,
    ):
        self.registrar = Registrar(registry, q_registry)
        self.run_no = RunNo(run_no_start_from - 1)
        self.run_no_count = RunNoCounter(run_no_start_from)
        self.registrar.script_change(
            script=self.statement, filename=self.filename
        )

    def initialize(self, state: State):
        self.run_no = self.run_no_count()
        self.registrar.state_initialized(self.run_no)
        self.registrar.state_change(state)
        self.state = state

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        if statement:
            self.statement = statement
            self.registrar.script_change(
                script=statement, filename=self.filename
            )
        if run_no_start_from is not None:
            self.run_no_count = RunNoCounter(run_no_start_from)

    async def run(self, state: State) -> Run:
        ret = await self.runner(
            self.func,
            RunArg(
                run_no=self.run_no,
                statement=self.statement,
                filename=self.filename,
            ),
        )
        self.registrar.run_start(self.run_no)
        self.registrar.state_change(state)
        self.state = state
        return ret

    def finish(self, state: State):
        self.registrar.run_end(state=state)
        self.registrar.state_change(state)
        self.state = state

    async def close(self, state: State):
        self.registrar.state_change(state)
        await to_thread(self.registrar.close)
        self.state = state


class Machine:
    """State machine

                 .-------------.
                 |   Created   |
                 '-------------'
                       |
                       V
                 .-------------.
            .--->| Initialized |---.
    reset() |    '-------------'   |
            |      |   | run()     |
            |------'   |           |
            |          v           |
            |    .-------------.   |
            |    |   Running   |   |
            |    '-------------'   |
            |          | finish()  |
            |          |           |
            |          V           |
            |    .-------------.   |  close()  .-------------.
            '----|  Finished   |-------------->|   Closed    |
                 '-------------'               '-------------'


    Parameters
    ----------
    statement : str
        A Python code as a string.
    run_no_start_from : int
        The run number of the first run

    """

    def __init__(self, statement: str, run_no_start_from=1):
        self.registry = SubscribableDict[Any, Any]()
        self._q_commands: QueueCommands = _mp.Queue()
        q_registry: QueueRegistry = _mp.Queue()
        executor_factory = partial(
            ProcessPoolExecutorWithLogging,
            max_workers=1,
            mp_context=_mp,
            initializer=run.set_queues,
            initargs=(self._q_commands, q_registry),
        )
        runner = partial(run_, executor_factory)  # type: ignore
        self._state: State = Created(
            self.registry,
            q_registry,
            runner,
            statement,
            run_no_start_from,
        )
        self._state = self._state.initialize()

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f"<{self.__class__.__name__} {self.state_name!r}>"

    @property
    def state_name(self) -> str:
        """e.g., "initialized", "running","""
        try:
            return self._state.name
        except BaseException:
            return "unknown"

    async def run(self) -> None:
        """Enter the running state"""
        self._state = await self._state.run()

    def send_pdb_command(
        self, command: str, prompt_no: int, trace_no: int
    ) -> None:
        self._q_commands.put((command, PromptNo(prompt_no), TraceNo(trace_no)))

    def interrupt(self) -> None:
        self._state.interrupt()

    def terminate(self) -> None:
        self._state.terminate()

    def kill(self) -> None:
        self._state.kill()

    async def finish(self) -> None:
        """Enter the finished state"""
        self._state = await self._state.finish()

    def exception(self) -> Optional[BaseException]:
        ret = self._state.exception()
        return ret

    def result(self) -> Any:
        return self._state.result()

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> None:
        """Enter the initialized state"""
        self._state = self._state.reset(statement, run_no_start_from)

    async def close(self) -> None:
        """Enter the closed state"""
        self._state = await self._state.close()
        await to_thread(self.registry.close)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        self._close()


class StateObsoleteError(Exception):
    """Operation on an obsolete state object."""

    pass


class StateMethodError(Exception):
    """Irrelevant operation on the state."""

    pass


class ObsoleteMixin:
    def assert_not_obsolete(self):
        if self.is_obsolete():
            raise StateObsoleteError(f"The state object is obsolete: {self!r}")

    def is_obsolete(self):
        return getattr(self, "_obsolete", False)

    def obsolete(self):
        self._obsolete = True


class State(ObsoleteMixin):
    """The base state class in the Nextline state machine"""

    name = "state"

    def __init__(self):
        self._context: Context

    def __repr__(self):
        # e.g., "<Initialized 'initialized'>"
        items = [self.__class__.__name__, repr(self.name)]
        if self.is_obsolete():
            items.append("obsolete")
        return f'<{" ".join(items)}>'

    def initialize(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def run(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def finish(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> State:
        del statement, run_no_start_from
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def close(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def interrupt(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def terminate(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def kill(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def exception(self) -> Optional[BaseException]:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def result(self) -> Any:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")


class Created(State):
    """The state "created" """

    name = "created"

    def __init__(
        self,
        registry: SubscribableDict[Any, Any],
        q_registry: QueueRegistry,
        runner: Callable[..., Coroutine[Any, Any, Run]],
        statement: str,
        run_no_start_from: int,
    ):
        filename = SCRIPT_FILE_NAME
        self._context = Context(
            state=self,
            registry=registry,
            q_registry=q_registry,
            run_no_start_from=run_no_start_from,
            statement=statement,
            filename=filename,
            runner=runner,
            func=run.run,
        )

    def initialize(self) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized(self)
        self.obsolete()
        return initialized


class Initialized(State):
    """The state "initialized", ready to run"""

    name = "initialized"

    def __init__(self, prev: State):
        self._context = prev._context
        self._context.initialize(self)

    @classmethod
    def as_reset(
        cls,
        prev: State,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        prev._context.reset(statement, run_no_start_from)
        return cls(prev)

    async def run(self) -> Running:
        self.assert_not_obsolete()
        running = await Running.create(self)
        self.obsolete()
        return running

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized.as_reset(self, statement, run_no_start_from)
        self.obsolete()
        return initialized

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        closed = await Closed.create(self)
        self.obsolete()
        return closed


class Running(State):
    """The state "running", the script is being executed."""

    name = "running"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        self._run = await self._context.run(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context
        self._run: Optional[Run] = None

    async def finish(self) -> Finished:
        self.assert_not_obsolete()
        assert self._run
        ret, exc = await self._run
        finished = Finished(self, result=ret, exception=exc)
        self.obsolete()
        return finished

    def interrupt(self) -> None:
        if self._run:
            self._run.interrupt()

    def terminate(self) -> None:
        if self._run:
            self._run.terminate()

    def kill(self) -> None:
        if self._run:
            self._run.kill()


class Finished(State):
    """The state "finished", the script execution has finished

    Parameters
    ----------
    context : object
        An instance of Context
    result : any
        The result of the script execution, always None
    exception : exception or None
        The exception of the script execution if any. Otherwise None

    """

    name = "finished"

    def __init__(
        self, prev: State, result: Any, exception: BaseException | None
    ):
        self._result = result
        self._exception = exception
        self._context = prev._context
        self._context.finish(self)

    def exception(self) -> Optional[BaseException]:
        """Return the exception of the script execution

        Return None if no exception has been raised.

        """
        return self._exception

    def result(self) -> Any:
        """Return the result of the script execution

        None in the current implementation as the build-in function
        exec() returns None.

        Re-raise the exception if an exception has been raised in the
        script execution.

        """

        if self._exception:
            raise self._exception

        return self._result

    async def finish(self) -> Finished:
        # This method can be called when Nextline.finish() is
        # asynchronously called multiple times.
        self.assert_not_obsolete()
        return self

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized.as_reset(self, statement, run_no_start_from)
        self.obsolete()
        return initialized

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        closed = await Closed.create(self)
        self.obsolete()
        return closed


class Closed(State):
    """The state "closed" """

    name = "closed"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.close(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        return self
