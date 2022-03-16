from __future__ import annotations

import asyncio
import dataclasses
from threading import Thread
import datetime
import itertools
import traceback
import json
from weakref import WeakKeyDictionary
from typing import TYPE_CHECKING, Dict, Optional, Any

from .trace import Trace
from .utils import (
    SubscribableDict,
    ThreadSafeAsyncioEvent,
    ThreadTaskIdComposer,
    to_thread,
)
from .call import call_with_trace
from .types import RunInfo
from . import script

if TYPE_CHECKING:
    from .pdb.ci import PdbCommandInterface

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
            |          | _exited() |
            |          |           |
            |          v           |
            |    .-------------.   |
            |    |   Exited    |   |
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
        self.registry = SubscribableDict()

        self.registry["statement"] = statement
        self.registry["script_file_name"] = SCRIPT_FILE_NAME

        run_no_count = itertools.count(run_no_start_from).__next__
        self.registry["run_no_count"] = run_no_count

        self.registry["trace_id_factory"] = ThreadTaskIdComposer()

        self.registry["run_no_map"] = WeakKeyDictionary()
        self.registry["trace_no_map"] = WeakKeyDictionary()

        self._lock_finish = asyncio.Condition()
        self._lock_close = asyncio.Condition()

        self._state: State = Initialized(self.registry)
        self._state_changed()

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f"<{self.__class__.__name__} {self.state_name!r}>"

    def _state_changed(self) -> None:
        self.registry["state_name"] = self.state_name
        if self.state_name == "running":
            self._run_info = RunInfo(
                run_no=self.registry["run_no"],
                state=self.state_name,
                script=self.registry["statement"],
                started_at=datetime.datetime.now(),
            )
            self.registry["run_info"] = self._run_info
        if self.state_name == "finished":
            exception = None
            if exc := self.exception():
                exception = "".join(
                    traceback.format_exception(
                        type(exc), exc, exc.__traceback__
                    )
                )
            result = None
            if not exception:
                result = json.dumps(self.result())
            self._run_info = dataclasses.replace(
                self._run_info,
                state=self.state_name,
                result=result,
                exception=exception,
                ended_at=datetime.datetime.now(),
            )
            # TODO: check if run_no matches
            self.registry["run_info"] = self._run_info

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
        self._task_exited = asyncio.create_task(self._exited())

    async def _exited(self) -> None:
        """Enter the exited state

        This method is scheduled as a task in run().

        Before changing the state to "exited", this method waits for the script
        execution (in another thread) to exit.
        """

        self._state = await self._state.exited()
        self._state_changed()

    def send_pdb_command(self, thread_asynctask_id, command) -> None:
        self._state.send_pdb_command(thread_asynctask_id, command)

    async def finish(self) -> None:
        """Enter the finished state"""
        await self._task_exited
        async with self._lock_finish:
            self._state = await self._state.finish()
            self._state_changed()

    def exception(self) -> Optional[Exception]:
        return self._state.exception()

    def result(self) -> Any:
        return self._state.result()

    def reset(self, statement: Optional[str] = None) -> None:
        """Enter the initialized state"""
        if statement:
            self.registry["statement"] = statement
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

    async def exited(self) -> State:
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
    registry : object
        An instance of Registry.

    """

    name = "initialized"

    def __init__(self, registry: SubscribableDict):
        self.registry = registry
        run_no = self.registry.get("run_no_count")()  # type: ignore
        self.registry["run_no"] = run_no
        self.registry["trace_id_factory"].reset()  # type: ignore

    def run(self):
        self.assert_not_obsolete()
        running = Running(self.registry)
        self.obsolete()
        return running

    def reset(self):
        self.assert_not_obsolete()
        initialized = Initialized(registry=self.registry)
        self.obsolete()
        return initialized

    def close(self):
        self.assert_not_obsolete()
        closed = Closed(self.registry)
        self.obsolete()
        return closed


class Running(State):
    """The state "running", the script is being executed.

    Parameters
    ----------
    registry : object
        An instance of Registry
    """

    name = "running"

    def __init__(self, registry: SubscribableDict):
        self.registry = registry
        self._event = ThreadSafeAsyncioEvent()

        statement = self.registry.get("statement")

        self._pdb_ci_map: Dict[int, PdbCommandInterface] = {}
        trace = Trace(
            registry=self.registry,
            pdb_ci_map=self._pdb_ci_map,
        )

        self.loop = asyncio.get_running_loop()

        def run():
            code = statement
            if isinstance(code, str):
                try:
                    code = compile(code, SCRIPT_FILE_NAME, "exec")
                except BaseException as e:
                    self._done(None, e)
                    return
            func = script.compose(code)
            result = None
            exception = None
            try:
                result = call_with_trace(func, trace)
            except BaseException as e:
                exception = e
            self._done(result, exception)

        self._thread = Thread(target=run, daemon=True)
        self._thread.start()

    def _done(self, result=None, exception=None):

        if self.loop.is_closed():
            # The exit is not being waited in the main thread, for example,
            # exited() is not called.
            return

        self._exited = Exited(
            self.registry,
            thread=self._thread,
            result=result,
            exception=exception,
        )

        try:
            self._event.set()
        except RuntimeError:
            # The event loop is closed.
            pass

    async def exited(self):
        """return the exited state after the script exits."""
        await self._event.wait()
        self.obsolete()
        return self._exited

    def send_pdb_command(self, trace_id: int, command: str) -> None:
        pdb_ci = self._pdb_ci_map[trace_id]
        pdb_ci.send_pdb_command(command)


class Exited(State):
    """The state "exited", the script execution has exited

    Parameters
    ----------
    registry : object
        An instance of Registry
    thread : object
        The object of the thread in which the script was executed.
        This thread is to be joined.
    result : any
        The result of the script execution, always None
    exception : exception or None
        The execution raised in the script execution if any. Otherwise
        None
    """

    name = "exited"

    def __init__(self, registry: SubscribableDict, thread, result, exception):
        self.registry = registry
        self._thread = thread
        self._result = result
        self._exception = exception

    async def finish(self):
        self.assert_not_obsolete()
        await to_thread(self._thread.join)
        finished = Finished(
            self.registry, result=self._result, exception=self._exception
        )
        self.obsolete()
        return finished


class Finished(State):
    """The state "finished", the script execution has finished

    The thread which executed the script has been joined.

    Parameters
    ----------
    registry : object
        An instance of Registry
    result : any
        The result of the script execution, always None
    exception : exception or None
        The exception of the script execution if any. Otherwise None

    """

    name = "finished"

    def __init__(self, registry: SubscribableDict, result, exception):
        self._result = result
        self._exception = exception

        self.registry = registry

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
        initialized = Initialized(registry=self.registry)
        self.obsolete()
        return initialized

    def close(self):
        self.assert_not_obsolete()
        closed = Closed(self.registry)
        self.obsolete()
        return closed


class Closed(State):
    """The state "closed"

    Parameters
    ----------
    registry : object
        An instance of Registry
    """

    name = "closed"

    def __init__(self, registry: SubscribableDict):
        self.registry = registry

    def close(self):
        self.assert_not_obsolete()
        return self
