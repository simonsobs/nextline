import asyncio
import threading
import itertools
from typing import Union

from .trace import Trace
from .utils import Registry, ThreadSafeAsyncioEvent
from .call import call_with_trace
from . import script

SCRIPT_FILE_NAME = "<string>"


# __________________________________________________________________||
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
        self.registry = Registry()
        self.registry.open_register("statement")
        self.registry.open_register("state_name")
        self.registry.open_register("script_file_name")
        self.registry.open_register("run_no")
        self.registry.open_register("run_no_count")
        self.registry.open_register_list("thread_task_ids")

        self.registry.register("statement", statement)
        self.registry.register("script_file_name", SCRIPT_FILE_NAME)
        self.registry.register(
            "run_no_count", itertools.count(run_no_start_from).__next__
        )

        self._state = Initialized(self.registry)

        self._lock_finish = asyncio.Condition()
        self._lock_close = asyncio.Condition()

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

    def run(self):
        """Enter the running state"""
        self._state = self._state.run()
        self._task_exited = asyncio.create_task(self._exited())

    async def _exited(self):
        """Enter the exited state

        This method is scheduled as a task in run().

        Bofore changing the state to "exited", this method waits for the script
        execution (in another thread) to exit.
        """

        self._state = await self._state.exited()

    def send_pdb_command(self, thread_asynctask_id, command):
        self._state.send_pdb_command(thread_asynctask_id, command)

    async def finish(self):
        """Enter the finished state"""
        await self._task_exited
        async with self._lock_finish:
            self._state = await self._state.finish()

    def exception(self):
        return self._state.exception()

    def result(self):
        self._state.result()

    def reset(self, statement: Union[str, None] = None):
        """Enter the initialized state"""
        if statement:
            self.registry.register("statement", statement)
        self._state = self._state.reset()

    async def close(self):
        """Enter the closed state"""
        async with self._lock_close:
            self._state = self._state.close()
            await self.registry.close()


# __________________________________________________________________||
class StateObsoleteError(Exception):
    """Operation on an obsolete state object."""

    pass


class StateMethodError(Exception):
    """Irrelevant operation on the state."""

    pass


# __________________________________________________________________||
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

    def __repr__(self):
        # e.g., "<Initialized 'initialized'>"
        items = [self.__class__.__name__, repr(self.name)]
        if self.is_obsolete():
            items.append("obsolete")
        return f'<{" ".join(items)}>'

    def run(self):
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def exited(self):
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    async def finish(self):
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def reset(self):
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def close(self):
        self.assert_not_obsolete()
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def send_pdb_command(self, *_, **__):
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def exception(self):
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")

    def result(self):
        raise StateMethodError(f"Irrelevant operation on the state: {self!r}")


class Initialized(State):
    """The state "initialized", ready to run

    Parameters
    ----------
    registry : object
        An instance of Registry.

    """

    name = "initialized"

    def __init__(self, registry: Registry):
        self.registry = registry
        run_no = self.registry.get("run_no_count")()
        self.registry.register("run_no", run_no)
        self.registry.register("state_name", self.name)

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

    def __init__(self, registry):
        self.registry = registry
        self._event = ThreadSafeAsyncioEvent()

        statement = self.registry.get("statement")

        trace = Trace(registry=self.registry)
        self.pdb_ci_registry = trace.pdb_ci_registry

        self.registry.register("state_name", self.name)

        self.loop = asyncio.get_running_loop()

        self._thread = threading.Thread(
            target=self._run, args=(statement, trace), daemon=True
        )
        self._thread.start()

    def _run(self, code, trace):

        if isinstance(code, str):
            try:
                code = compile(code, SCRIPT_FILE_NAME, "exec")
            except BaseException as e:
                self._done(None, e)
                return

        func = script.compose(code)

        call_with_trace(func, trace, self._done)

    def _done(self, result=None, exception=None):
        # callback function, to be called from another thread at the
        # end of _run()

        if self.loop.is_closed():
            # The exit is not being waited in the main thread, for
            # example, neither exited() of finish() is called.
            return

        self._exited = Exited(
            self.registry,
            thread=self._thread,
            result=result,
            exception=exception,
        )

        self.obsolete()

        try:
            self._event.set()
        except RuntimeError:
            # The event loop is closed.
            pass

    async def exited(self):
        """return the exited state after the script exits."""
        await self._event.wait()
        return self._exited

    def send_pdb_command(self, thread_asynctask_id, command):
        pdb_ci = self.pdb_ci_registry.get_ci(thread_asynctask_id)
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

    def __init__(self, registry, thread, result, exception):
        self.registry = registry
        self._thread = thread
        self._result = result
        self._exception = exception

        self.registry.register("state_name", self.name)

    async def finish(self):
        self.assert_not_obsolete()
        await self._join(self._thread)
        finished = Finished(
            self.registry, result=self._result, exception=self._exception
        )
        self.obsolete()
        return finished

    async def _join(self, thread):
        try:
            await asyncio.to_thread(thread.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, thread.join)


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

    def __init__(self, registry, result, exception):
        self._result = result
        self._exception = exception

        self.registry = registry
        self.registry.register("state_name", self.name)

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

    def __init__(self, registry):
        self.registry = registry
        self.registry.register("state_name", self.name)

    def close(self):
        self.assert_not_obsolete()
        return self


# __________________________________________________________________||
