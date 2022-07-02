from __future__ import annotations

from dataclasses import dataclass, InitVar, field
from functools import partial
import multiprocessing as mp
from tblib import pickling_support  # type: ignore
from typing import Callable, Coroutine, Optional, Any

from .utils import (
    SubscribableDict,
    to_thread,
    ProcessPoolExecutorWithLogging,
    run_in_process,
    RunInProcess,
)
from .process import run
from .process.run import QueueRegistry, RunArg, QueueCommands
from .registrar import Registrar
from .types import RunNo
from .count import RunNoCounter

pickling_support.install()

SCRIPT_FILE_NAME = "<string>"


@dataclass
class Context:
    statement: str
    filename: str
    runner: Callable[..., Coroutine[Any, Any, RunInProcess]]
    func: Callable
    registry: InitVar[SubscribableDict[Any, Any]]
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
        self.result = None
        self.exception = None
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

    async def run(self, state: State) -> RunInProcess:
        self.future = await self.runner(
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
        self.registrar.run_end(state=state)
        self.registrar.state_change(state)
        self.state = state

    async def close(self, state: State):
        self.registrar.state_change(state)
        await to_thread(self.registrar.close)
        self.state = state


def build_context(
    registry: SubscribableDict[Any, Any],
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
    return Context(
        registry=registry,
        q_registry=q_registry,
        run_no_start_from=run_no_start_from,
        statement=statement,
        filename=filename,
        runner=runner,
        func=run.run,
    )


class Machine:
    """State machine

                 .-------------.
                 |   Created   |---.
                 '-------------'   |
                       |           |
                       V           |
                 .-------------.   |
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

    """

    def __init__(self, context: Context):
        self._context = context
        self._state: State = Created(self._context)
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

    def reset(self, *args, **kwargs) -> None:
        """Enter the initialized state"""
        self._state = self._state.reset(*args, **kwargs)

    async def close(self) -> None:
        """Enter the closed state"""
        self._state = await self._state.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()


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

    def reset(self, *_, **__) -> State:
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

    def __init__(self, context: Context):
        self._context = context

    def initialize(self) -> Initialized:
        self.assert_not_obsolete()
        next = Initialized(self)
        self.obsolete()
        return next

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        next = await Closed.create(self)
        self.obsolete()
        return next


class Initialized(State):
    """The state "initialized", ready to run"""

    name = "initialized"

    def __init__(self, prev: State):
        self._context = prev._context
        self._context.initialize(self)

    async def run(self) -> Running:
        self.assert_not_obsolete()
        next = await Running.create(self)
        self.obsolete()
        return next

    def reset(self, *args, **kwargs) -> Initialized:
        self.assert_not_obsolete()
        self._context.reset(*args, **kwargs)
        next = Initialized(self)
        self.obsolete()
        return next

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        next = await Closed.create(self)
        self.obsolete()
        return next


class Running(State):
    """The state "running", the script is being executed."""

    name = "running"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.run(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    async def finish(self) -> Finished:
        self.assert_not_obsolete()
        next = await Finished.create(self)
        self.obsolete()
        return next

    def interrupt(self) -> None:
        self._context.interrupt()

    def terminate(self) -> None:
        self._context.terminate()

    def kill(self) -> None:
        self._context.kill()


class Finished(State):
    """The state "finished", the script execution has finished"""

    name = "finished"

    @classmethod
    async def create(cls, prev: State):
        self = cls(prev)
        await self._context.finish(self)
        return self

    def __init__(self, prev: State):
        self._context = prev._context

    def exception(self) -> Optional[BaseException]:
        """Return the exception of the script execution

        Return None if no exception has been raised.

        """
        return self._context.exception

    def result(self) -> Any:
        """Return the result of the script execution

        None in the current implementation as the build-in function
        exec() returns None.

        Re-raise the exception if an exception has been raised in the
        script execution.

        """

        if exc := self._context.exception:
            raise exc

        return self._context.result

    async def finish(self) -> Finished:
        self.assert_not_obsolete()
        return self

    def reset(self, *args, **kwargs) -> Initialized:
        self.assert_not_obsolete()
        self._context.reset(*args, **kwargs)
        next = Initialized(self)
        self.obsolete()
        return next

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        next = await Closed.create(self)
        self.obsolete()
        return next


class Closed(State):
    """The state "closed" """

    name = "closed"

    @classmethod
    async def create(cls, prev: State):
        return cls(prev)

    def __init__(self, prev: State):
        self._context = prev._context

    async def close(self) -> Closed:
        self.assert_not_obsolete()
        return self
