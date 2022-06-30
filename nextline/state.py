from __future__ import annotations

from queue import Queue
from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

import os
import signal
import asyncio

import dataclasses
from functools import partial
import multiprocessing as mp
from tblib import pickling_support  # type: ignore
from typing import (
    Callable,
    Coroutine,
    Generic,
    Optional,
    Any,
    Tuple,
    TypeVar,
)
from typing_extensions import ParamSpec

from .utils import SubscribableDict, to_thread, MultiprocessingLogging
from .process import run
from .process.run import RunArg, QueueCommands
from .registrar import Registrar
from .types import PromptNo, RunNo, TraceNo
from .count import RunNoCounter

_mp = mp.get_context("spawn")  # NOTE: monkey patched in tests

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


def initializer(
    init_logging: Callable[[], Any],
    q_commands: QueueCommands,
    q_registry: Queue[Tuple[str, Any, bool]],
):
    init_logging()
    run.set_queues(q_commands, q_registry)


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


@dataclasses.dataclass
class Context:
    registrar: Registrar
    mp_logging: MultiprocessingLogging
    run_no_count: Callable[[], RunNo]
    run_no: RunNo
    statement: str
    filename: str
    runner: Callable[..., Coroutine[Any, Any, Run]]
    func: Callable
    run: Optional[Callable] = None


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

    """

    def __init__(self, statement: str, run_no_start_from=1):
        filename = SCRIPT_FILE_NAME
        self.registry = SubscribableDict[Any, Any]()
        queue = _mp.Queue()

        self._q_commands: QueueCommands = _mp.Queue()

        mp_logging = MultiprocessingLogging(context=_mp)

        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=_mp,
            initializer=initializer,
            initargs=(mp_logging.init, self._q_commands, queue),
        )

        run_no = RunNo(run_no_start_from - 1)
        registrar = Registrar(self.registry, queue)

        self._context = Context(
            registrar=registrar,
            mp_logging=mp_logging,
            run_no_count=RunNoCounter(run_no_start_from),
            run_no=run_no,
            statement=statement,
            filename=filename,
            runner=partial(run_, executor_factory),
            func=run.run,
        )

        self._state: State = Created(
            self._context,
            self.registry,
            self._q_commands,
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

    def exception(self) -> Optional[Exception]:
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
        await to_thread(self._close)

    def _close(self) -> None:
        self._state = self._state.close()
        self.registry.close()

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

    def close(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def interrupt(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def terminate(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def kill(self) -> None:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def exception(self) -> Optional[Exception]:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def result(self) -> Any:
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")


class Created(State):
    """The state "created" """

    name = "created"

    def __init__(
        self,
        context: Context,
        registry: SubscribableDict[Any, Any],
        q_commands: QueueCommands,
        statement: str,
        run_no_start_from: int,
    ):
        self._context = context
        self._context.registrar.script_change(
            script=self._context.statement, filename=self._context.filename
        )

    def initialize(self) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized(self._context)
        self.obsolete()
        return initialized


class Initialized(State):
    """The state "initialized", ready to run

    Parameters
    ----------
    context : dict
        An instance of Context

    """

    name = "initialized"

    def __init__(
        self,
        context: Context,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ):
        self._context = context
        if statement:
            self._context.statement = statement
            self._context.registrar.script_change(
                script=statement, filename=self._context.filename
            )
        if run_no_start_from is not None:
            self._context.run_no_count = RunNoCounter(run_no_start_from)
        self._context.run_no = self._context.run_no_count()
        self._context.registrar.state_initialized(self._context.run_no)
        self._context.registrar.state_change(self)

    async def run(self) -> Running:
        self.assert_not_obsolete()
        running = await Running.create(self._context)
        self.obsolete()
        return running

    def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized(self._context, statement, run_no_start_from)
        self.obsolete()
        return initialized

    def close(self) -> Closed:
        self.assert_not_obsolete()
        closed = Closed(self._context)
        self.obsolete()
        return closed


class Running(State):
    """The state "running", the script is being executed.

    Parameters
    ----------
        An instance of Context
    """

    name = "running"

    @classmethod
    async def create(cls, context: Context):
        self = cls(context)
        context.run = partial(
            context.runner,
            context.func,
            RunArg(
                run_no=context.run_no,
                statement=context.statement,
                filename=context.filename,
            ),
        )
        assert context.run
        self._run = await context.run()
        self._context.registrar.run_start(self._context.run_no)
        self._context.registrar.state_change(self)
        return self

    def __init__(self, context: Context):
        self._context = context
        self._run: Optional[Run] = None

    async def finish(self) -> Finished:
        self.assert_not_obsolete()
        assert self._run
        ret, exc = await self._run
        finished = Finished(self._context, result=ret, exception=exc)
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
    context : dict
        An instance of Context
    result : any
        The result of the script execution, always None
    exception : exception or None
        The exception of the script execution if any. Otherwise None

    """

    name = "finished"

    def __init__(self, context: Context, result, exception):
        self._result = result
        self._exception = exception
        self._context = context
        self._context.registrar.run_end(state=self)
        self._context.registrar.state_change(self)

    def exception(self):
        """Return the exception of the script execution

        Return None if no exception has been raised.

        """
        return self._exception

    def result(self):
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
        initialized = Initialized(self._context, statement, run_no_start_from)
        self.obsolete()
        return initialized

    def close(self) -> Closed:
        self.assert_not_obsolete()
        closed = Closed(self._context)
        self.obsolete()
        return closed


class Closed(State):
    """The state "closed" """

    name = "closed"

    def __init__(self, context: Context):
        self._context = context
        self._context.registrar.state_change(self)
        self._context.registrar.close()
        self._context.mp_logging.close()

    def close(self) -> Closed:
        self.assert_not_obsolete()
        return self
