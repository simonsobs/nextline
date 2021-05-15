import asyncio
import threading
import warnings
from typing import Optional, Callable

from .registry import Registry
from .trace import Trace
from .utils import ThreadSafeAsyncioEvent
from .exec_ import exec_with_trace

SCRIPT_FILE_NAME = '<string>'

##__________________________________________________________________||
class State:
    """The base state class in the Nextline state machine
    """
    def run(self):
        return self
    async def finish(self):
        return self
    async def close(self):
        return self
    def send_pdb_command(self, *_, **__):
        pass
    def exception(self):
        return None
    def result(self):
        return None

class Initialized(State):
    """The state "initialized", ready to run

    Parameters
    ----------
    statement : str
        A Python code as a string
    exited : callable, optional
        A callable with one argument, usually Nextline._exited(state).
        It will be called with the state object Exited after the
        script has exited.
    """

    name = "initialized"

    def __init__(self, statement: str, exited: Optional[Callable] = None):
        self._exited = exited
        self._next = None

        self.registry = Registry()
        self.registry.register_statement(statement)
        self.registry.register_script_file_name(SCRIPT_FILE_NAME)
        self.registry.register_state_name(self.name)

    def run(self):
        if not self._next:
            self._next = Running(self.registry, self._exited)
        return self._next

class Running(State):
    """The state "running", the script is being executed.

    Parameters
    ----------
    registry : object
        An instance of Registry
    exited : callable
        see Initialized

    """

    name = "running"

    def __init__(self, registry, exited):
        self.registry = registry
        self._callback_func = exited
        self._event_exited = ThreadSafeAsyncioEvent()
        self._next = None

        trace = Trace(
            registry=self.registry,
            modules_to_trace={exec_with_trace.__module__}
        )
        self.pdb_ci_registry = trace.pdb_ci_registry

        statement = self.registry.statement

        if isinstance(statement, str):
            code = compile(statement, self.registry.script_file_name, 'exec')
        else:
            code = statement

        self.registry.register_state_name(self.name)

        self._thread = threading.Thread(
            target=exec_with_trace,
            args=(code, trace, self._done),
            daemon=True
        )
        self._thread.start()

    def _done(self, result=None, exception=None):
        # callback function, to be called from another thread at the
        # end of exec_with_trace()
        self._state_exited = Exited(
            self.registry,
            thread=self._thread,
            result=result,
            exception=exception
        )
        if self._callback_func:
            try:
                self._callback_func(self._state_exited)
            except BaseException as e:
                warnings.warn(f'An exception occurred in the callback: {e}')
        self._event_exited.set()

    async def finish(self):
        if not self._next:
            await self._event_exited.wait()
            self._event_exited.clear()
            self._next = await self._state_exited.finish()
        return self._next

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

        self._next = None

        self.registry.register_state_name(self.name)

    async def finish(self):
        if not self._next:
            await self._join(self._thread)
            self._next = Finished(self.registry, result=self._result, exception=self._exception)
        return self._next

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

        self._next = None

        self.registry = registry
        self.registry.register_state_name(self.name)

    def exception(self):
        """Return the exception of the script execution

        Return None if no execution has been raised.

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

    async def close(self):
        if not self._next:
            self._next = Closed(self.registry)
            await self._next._ainit()
        return self._next

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
        self.registry.register_state_name(self.name)

    async def _ainit(self):
        await self.registry.close() # close here because "await" is
                                    # not allowed in __init__()

##__________________________________________________________________||
