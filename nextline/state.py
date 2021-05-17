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
class ObsoleteMixin:
    def assert_not_obsolete(self):
        if self.is_obsolete():
            raise Exception(f'The state is obsolete: {self!r}')
    def is_obsolete(self):
        return getattr(self, "_obsolete", False)
    def obsolete(self):
        self._obsolete = True

class State(ObsoleteMixin):
    """The base state class in the Nextline state machine
    """
    def __repr__(self):
        # e.g., "<Initialized 'initialized'>"
        items = [self.__class__.__name__, repr(self.name)]
        if self.is_obsolete():
            items.append('obsolete')
        return f'<{" ".join(items)}>'
    def run(self):
        return self
    async def finish(self):
        return self
    def reset(self):
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
    registry : object, optional
        An instance of Registry. This parameter will be given by a state
        object when the state is reset.

    """

    name = "initialized"

    def __init__(self, statement: str, exited: Optional[Callable] = None,
                 registry: Optional[Registry] = None):
        self._exited = exited

        if registry:
            self.registry = registry
        else:
            self.registry = Registry()

        self.registry.register_statement(statement)
        self.registry.register_script_file_name(SCRIPT_FILE_NAME)
        self.registry.register_state_name(self.name)

    def run(self):
        self.assert_not_obsolete()
        running = Running(self.registry, self._exited)
        self.obsolete()
        return running

    async def close(self):
        self.assert_not_obsolete()
        closed = Closed(self.registry, self._exited)
        await closed._ainit()
        self.obsolete()
        return closed

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
        self._exited = exited
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
            self._exited,
            thread=self._thread,
            result=result,
            exception=exception
        )

        if self._exited:
            try:
                self._exited(self._state_exited)
            except BaseException as e:
                warnings.warn(f'An exception occurred in the callback: {e}')

        try:
            self._event_exited.set()
        except RuntimeError:
            # The Event loop is closed.
            # This can happen when finish() is not called.
            pass

    async def finish(self):
        if not self._next:
            await self._event_exited.wait()
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
    exited : callable
        see Initialized
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

    def __init__(self, registry, exited, thread, result, exception):
        self.registry = registry
        self._exited = exited
        self._thread = thread
        self._result = result
        self._exception = exception

        self._next = None

        self.registry.register_state_name(self.name)

    async def finish(self):
        if not self._next:
            await self._join(self._thread)
            self._next = Finished(
                self.registry, self._exited,
                result=self._result,
                exception=self._exception
            )
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
    exited : callable
        see Initialized
    result : any
        The result of the script execution, always None
    exception : exception or None
        The exception of the script execution if any. Otherwise None

    """

    name = "finished"

    def __init__(self, registry, exited, result, exception):
        self._exited = exited

        self._result = result
        self._exception = exception

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

    def reset(self):
        self.assert_not_obsolete()
        statement = self.registry.statement
        initialized = Initialized(
            statement=statement,
            exited=self._exited,
            registry=self.registry
        )
        self.obsolete()
        return initialized

    async def close(self):
        self.assert_not_obsolete()
        closed = Closed(self.registry, self._exited)
        await closed._ainit()
        self.obsolete()
        return closed

class Closed(State):
    """The state "closed"

    Parameters
    ----------
    registry : object
        An instance of Registry
    exited : callable
        see Initialized
    """

    name = "closed"

    def __init__(self, registry, exited):
        self._exited = exited

        self.registry = registry
        self.registry.register_state_name(self.name)

    async def _ainit(self):
        await self.registry.close() # close here because "await" is
                                    # not allowed in __init__()

##__________________________________________________________________||
