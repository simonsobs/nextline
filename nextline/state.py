from __future__ import annotations

from queue import Queue
from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

import os
import signal
import asyncio

from functools import partial
import multiprocessing as mp
from tblib import pickling_support  # type: ignore
from typing import Callable, Generic, Optional, Any, Tuple, TypedDict, TypeVar
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


class Context(TypedDict):
    executor_factory: Callable[[], Executor]
    run: Callable[..., Any]
    run_arg: RunArg


class Machine:
    """State machine

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
        self._run_no = RunNo(run_no_start_from - 1)
        self._run_no_count = RunNoCounter(run_no_start_from)
        queue = _mp.Queue()
        self._registrar = Registrar(self.registry, queue)

        self._q_commands: QueueCommands = _mp.Queue()

        self._mp_logging = MultiprocessingLogging(context=_mp)

        executor_factory = partial(
            ProcessPoolExecutor,
            max_workers=1,
            mp_context=_mp,
            initializer=initializer,
            initargs=(self._mp_logging.init, self._q_commands, queue),
        )

        self._run_arg = RunArg(
            statement=statement,
            filename=filename,
        )

        self.context = Context(
            executor_factory=executor_factory,
            run=run.run,
            run_arg=self._run_arg,
        )

        self._registrar.script_change(script=statement, filename=filename)

        self._lock_finish = asyncio.Condition()
        self._lock_close = asyncio.Condition()

        self._state: State = Initialized(self.context)
        self._state_changed()

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f"<{self.__class__.__name__} {self.state_name!r}>"

    def _state_changed(self) -> None:
        self._registrar.state_change(self._state)
        if self._state.name == "initialized":
            self._run_no = self._run_no_count()
            self._run_arg["run_no"] = self._run_no
            self._registrar.state_initialized(self._run_no)
        elif self._state.name == "running":
            self._registrar.run_start(self._run_no)
        elif self._state.name == "finished":
            self._registrar.run_end(state=self._state)

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
        self._state_changed()

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
        async with self._lock_finish:
            self._state = await self._state.finish()
            self._state_changed()

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
        if statement:
            self._run_arg["statement"] = statement
            self._registrar.script_change(
                script=statement, filename=SCRIPT_FILE_NAME
            )
        if run_no_start_from is not None:
            self._run_no_count = RunNoCounter(run_no_start_from)
            # self._registrar.reset_run_no_count(run_no_start_from)
        self._state = self._state.reset()
        self._state_changed()

    async def close(self) -> None:
        """Enter the closed state"""
        async with self._lock_close:
            await to_thread(self._close)

    def _close(self) -> None:
        self._state = self._state.close()
        self._state_changed()
        self._registrar.close()
        self.registry.close()
        self._mp_logging.close()

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

    async def run(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def finish(self) -> State:
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def reset(self) -> State:
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


class Initialized(State):
    """The state "initialized", ready to run

    Parameters
    ----------
    context : dict
        An instance of Context

    """

    name = "initialized"

    def __init__(self, context: Context):
        self._context = context

    async def run(self) -> Running:
        self.assert_not_obsolete()
        running = await Running.create(self._context)
        self.obsolete()
        return running

    def reset(self) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized(context=self._context)
        self.obsolete()
        return initialized

    def close(self) -> Closed:
        self.assert_not_obsolete()
        closed = Closed()
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
        executor_factory = context["executor_factory"]
        func = context["run"]
        func_arg = context["run_arg"]
        self._run = await run_(executor_factory, func, func_arg)
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

    def reset(self) -> Initialized:
        self.assert_not_obsolete()
        initialized = Initialized(context=self._context)
        self.obsolete()
        return initialized

    def close(self) -> Closed:
        self.assert_not_obsolete()
        closed = Closed()
        self.obsolete()
        return closed


class Closed(State):
    """The state "closed" """

    name = "closed"

    def close(self) -> Closed:
        self.assert_not_obsolete()
        return self
