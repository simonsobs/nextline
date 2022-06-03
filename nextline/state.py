from __future__ import annotations

import asyncio
import dataclasses
import datetime
import itertools
import traceback
import json
from queue import Queue
from weakref import WeakKeyDictionary
from typing import Optional, Any, Tuple

from .io import IOSubscription
from .utils import (
    ExcThread,
    SubscribableDict,
    ThreadTaskIdComposer,
    to_thread,
)
from .run import run, Context
from .types import RunInfo


SCRIPT_FILE_NAME = "<string>"


class Registrar:
    def __init__(self, run_no_start_from):
        self._registry = SubscribableDict[Any, Any]()

        run_no_count = itertools.count(run_no_start_from).__next__
        self._registry["run_no_count"] = run_no_count

        self._registry["trace_id_factory"] = ThreadTaskIdComposer()

        self._registry["run_no_map"] = WeakKeyDictionary()
        self._registry["trace_no_map"] = WeakKeyDictionary()

    def script_change(
        self, script: str, filename: str = SCRIPT_FILE_NAME
    ) -> None:
        self._registry["statement"] = script
        self._registry["script_file_name"] = filename

    def state_change(self, state: State) -> None:
        self._registry["state_name"] = state.name

    def run_start(self):
        self._run_info = RunInfo(
            run_no=self._registry["run_no"],
            state="running",
            script=self._registry["statement"],
            started_at=datetime.datetime.now(),
        )
        self._registry["run_info"] = self._run_info

    def run_end(self, result, exception) -> None:
        if exception:
            exception = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
        if not exception:
            result = json.dumps(result)
        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=result,
            exception=exception,
            ended_at=datetime.datetime.now(),
        )
        # TODO: check if run_no matches
        self._registry["run_info"] = self._run_info


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
        self.registrar = Registrar(run_no_start_from=run_no_start_from)

        registry = self.registrar._registry
        self.registry = registry

        self.context = Context(
            statement=statement,
            filename=filename,
            create_capture_stdout=IOSubscription(registry),
            registry=registry,
        )

        self.registrar.script_change(script=statement, filename=filename)

        self._lock_finish = asyncio.Condition()
        self._lock_close = asyncio.Condition()

        self._state: State = Initialized(self.context)
        self._state_changed()

    def __repr__(self):
        # e.g., "<Machine 'running'>"
        return f"<{self.__class__.__name__} {self.state_name!r}>"

    def _state_changed(self) -> None:
        self.registrar.state_change(self._state)
        if self.state_name == "running":
            self.registrar.run_start()
        if self.state_name == "finished":
            exception = self.exception()
            result = self.result() if not exception else None
            self.registrar.run_end(result, exception)

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
            self.registrar.script_change(script=statement)
        if run_no_start_from is not None:
            run_no_count = itertools.count(run_no_start_from).__next__
            self.registry["run_no_count"] = run_no_count
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
        registry = context["registry"]
        run_no = registry.get("run_no_count")()  # type: ignore
        registry["run_no"] = run_no
        registry["trace_id_factory"].reset()  # type: ignore

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
