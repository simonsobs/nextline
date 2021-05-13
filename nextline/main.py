import asyncio
import threading

from .registry import Registry
from .trace import Trace
from .utils import QueueDist, ThreadSafeAsyncioEvent
from .exec_ import exec_with_trace

SCRIPT_FILE_NAME = '<string>'

##__________________________________________________________________||
class Nextline:
    """Nextline allows line-by-line execution of concurrent Python scripts

    Nextline supports concurrency with threading and asyncio. It uses
    multiple instances of Pdb, one for each thread and async task.

    Note
    ----
    The running asyncio event loop must exists when Nextline is
    instantiated.

    Parameters
    ----------
    statement : str
        A Python code as a string

    """

    def __init__(self, statement):
        self._queue_state_name = QueueDist()
        self._event_run = threading.Event()

        self._state = Initialized()
        self._queue_state_name.put(self._state.name)
        self.registry = self._state.registry
        self.registry.register_statement(statement)
        self.registry.register_script_file_name(SCRIPT_FILE_NAME)

    @property
    def global_state(self) -> str:
        """state, e.g., "initialized", "running", "finished"
        """
        return self._state.name

    def run(self):
        """run the script
        """
        self._state = self._state.run(
            registry=self.registry,
            exited=self._exited
        )
        self._queue_state_name.put(self._state.name)
        self._event_run.set()

    def _exited(self, state):
        """callback function for the script execution

        This method is to be called by Running from the thread that
        executes the script when the execution has exited.

        """
        self._event_run.wait() # in case the script finishes too quickly
        self._event_run.clear()
        self._state = state
        self._queue_state_name.put(self._state.name)

    async def wait(self):
        """wait for the script execution to finish
        """
        self._state = await self._state.wait()
        self._queue_state_name.put(self._state.name)
        await self.registry.close()
        await self._queue_state_name.close()

    async def subscribe_global_state(self):
        async for y in self._queue_state_name.subscribe():
            yield y

    async def subscribe_thread_asynctask_ids(self):
        async for y in self.registry.subscribe_thread_task_ids():
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        async for y in self.registry.subscribe_thread_task_state(thread_asynctask_id):
            yield y

    def send_pdb_command(self, thread_asynctask_id, command):
        self._state.send_pdb_command(thread_asynctask_id, command)

    def get_source(self, file_name=None):
        return self.registry.get_source(file_name=file_name)

    def get_source_line(self, line_no, file_name=None):
        return self.registry.get_source_line(line_no=line_no, file_name=file_name)

##__________________________________________________________________||
class State:
    """The base state class in the Nextline state machine
    """
    def run(self, *_, **__):
        return self
    async def wait(self):
        pass
    def send_pdb_command(self, *_, **__):
        pass

class Initialized(State):
    """The state "initialized", ready to run
    """
    name = "initialized"
    def __init__(self):
        self.registry = Registry()
    def run(self, *args, **kwargs):
        return Running(*args, **kwargs)

class Running(State):
    """The state "running", the script is being executed.

    Parameters
    ----------
    registry : object
        An instance of Registry
    exited : callable
        A callable with one argument, usually
        Nextline._exited(state). It will be called with the next
        state object (Finished) after the script has exited.

    """

    name = "running"

    def __init__(self, registry, exited):
        self._callback_func = exited
        self._event_exited = ThreadSafeAsyncioEvent()

        trace = Trace(
            registry=registry,
            modules_to_trace={exec_with_trace.__module__}
        )
        self.pdb_ci_registry = trace.pdb_ci_registry

        statement = registry.statement

        if isinstance(statement, str):
            code = compile(statement, registry.script_file_name, 'exec')
        else:
            code = statement

        self.thread = threading.Thread(
            target=exec_with_trace,
            args=(code, trace, self._done),
            daemon=True
        )
        self.thread.start()

    def _done(self, exception=None):
        # callback function, to be called from another thread at the
        # end of exec_with_trace()
        self._state_exited = Exited(thread=self.thread, exception=exception)
        self._event_exited.set()
        self._callback_func(self._state_exited)

    async def wait(self):
        await self._event_exited.wait()
        self._event_exited.clear()
        return await self._state_exited.wait()

    def send_pdb_command(self, thread_asynctask_id, command):
        pdb_ci = self.pdb_ci_registry.get_ci(thread_asynctask_id)
        pdb_ci.send_pdb_command(command)


class Exited(State):
    """The state "exited", the script execution has exited

    Parameters
    ----------
    thread : object
        The object of the thread in which the script was executed.
        This thread is to be joined.
    exception : exception or None
        The execution raised in the script execution if any. Otherwise
        None
    """

    name = "exited"
    def __init__(self, thread, exception):
        self.thread = thread
        self.exception = exception
    async def wait(self):
        if self.thread:
            await self._join(self.thread)
        return Finished(exception=self.exception)
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
    exception : exception or None
        The execution raised in the script execution if any. Otherwise
        None
    """

    name = "finished"
    def __init__(self, exception):
        self.exception = exception

##__________________________________________________________________||
