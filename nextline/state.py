from __future__ import annotations

import asyncio
from queue import Queue
from typing import Optional, Any, Tuple

from .io import IOSubscription
from .utils import ExcThread, SubscribableDict, to_thread
from .run import run, Context
from .registrar import Registrar


SCRIPT_FILE_NAME = "<string>"


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
        self._registrar = Registrar(self.registry, run_no_start_from)

        self.context = Context(
            statement=statement,
            filename=filename,
            create_capture_stdout=IOSubscription(
                self.registry,
                self.registry["run_no_map"],
                self.registry["trace_no_map"],
            ),
            registry=self.registry,
            registrar=self._registrar,
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

    @property
    def state_name(self) -> str:
        """e.g., "initialized", "running","""
        try:
            return self._state.name
        except BaseException:
            return "unknown"

    def run(self) -> None:
        """Enter the running state"""
        self._state = self._state.run()
        self._state_changed()

    def send_pdb_command(self, trace_id, command) -> None:
        self._state.send_pdb_command(trace_id, command)

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
            self.context["statement"] = statement
            self._registrar.script_change(
                script=statement, filename=SCRIPT_FILE_NAME
            )
        if run_no_start_from is not None:
            self._registrar.reset_run_no_count(run_no_start_from)
        self._state = self._state.reset()
        self._state_changed()

    async def close(self) -> None:
        """Enter the closed state"""
        async with self._lock_close:
            self._state = self._state.close()
            self._state_changed()
            await to_thread(self.registry.close)


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

    def run(self) -> State:
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

    def send_pdb_command(self, trace_id: int, command: str) -> None:
        del trace_id, command
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

    def run(self):
        self.assert_not_obsolete()
        running = Running(self._context)
        self.obsolete()
        return running

    def reset(self):
        self.assert_not_obsolete()
        initialized = Initialized(context=self._context)
        self.obsolete()
        return initialized

    def close(self):
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

    def __init__(self, context: Context):
        self._context = context
        self._q_commands: Queue[Tuple[int, str]] = Queue()
        self._q_done: Queue[Tuple[Any, Any]] = Queue()

        self._thread = ExcThread(
            target=run,
            args=(context, self._q_commands, self._q_done),
            daemon=True,
        )
        self._thread.start()

    async def finish(self):
        self.assert_not_obsolete()
        ret, exc = await to_thread(self._q_done.get)
        await to_thread(self._thread.join)
        finished = Finished(self._context, result=ret, exception=exc)
        self.obsolete()
        return finished

    def send_pdb_command(self, trace_id: int, command: str) -> None:
        self._q_commands.put((trace_id, command))


class Finished(State):
    """The state "finished", the script execution has finished

    The thread which executed the script has been joined.

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

    async def finish(self):
        # This method can be called when Nextline.finish() is
        # asynchronously called multiple times.
        self.assert_not_obsolete()
        return self

    def reset(self):
        self.assert_not_obsolete()
        initialized = Initialized(context=self._context)
        self.obsolete()
        return initialized

    def close(self):
        self.assert_not_obsolete()
        closed = Closed()
        self.obsolete()
        return closed


class Closed(State):
    """The state "closed" """

    name = "closed"

    def close(self):
        self.assert_not_obsolete()
        return self
