import asyncio
import threading
import linecache

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
        self.statement = statement
        self._queue_state_name = QueueDist()
        self.registry = Registry()
        self._event_run = threading.Event()
        self._event_finished = ThreadSafeAsyncioEvent()
        self._state = Initialized()
        self._queue_state_name.put(self._state.name)

    @property
    def global_state(self) -> str:
        """state, e.g., "initialized", "running", "finished"
        """
        return self._state.name

    def run(self):
        """run the script
        """
        self._state = self._state.run(
            statement=self.statement,
            registry=self.registry,
            finished=self._finished
        )
        self._queue_state_name.put(self._state.name)
        self._event_run.set()

    def _finished(self, state):
        """change the state to "finished"

        This method is to be called by state object Running from the
        thread that executes the script.

        """
        self._event_run.wait() # in case the script finishes too quickly
        self._event_run.clear()
        self._state = state
        self._queue_state_name.put(self._state.name)
        self._event_finished.set()

    async def wait(self):
        await self._event_finished.wait()
        self._event_finished.clear()
        await self._state.wait()
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
        if not file_name or file_name == SCRIPT_FILE_NAME:
            return self.statement.split('\n')
        return [l.rstrip() for l in linecache.getlines(file_name)]

    def get_source_line(self, line_no, file_name=None):
        '''
        based on linecache.getline()
        https://github.com/python/cpython/blob/v3.9.5/Lib/linecache.py#L26
        '''
        lines = self.get_source(file_name)
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ''

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
    def run(self, *args, **kwargs):
        return Running(*args, **kwargs)

class Running(State):
    """The state "running", the script is being executed.

    Parameters
    ----------
    statement : str
        A Python code as a string
    registry : object
        An instance of Registry
    finished : callable
        A callable with one argument. This will be called with the
        next state object when the script execution finishes.

    """

    name = "running"

    def __init__(self, statement, registry, finished):
        self.finished = finished

        trace = Trace(
            registry=registry,
            modules_to_trace={exec_with_trace.__module__}
        )
        self.pdb_ci_registry = trace.pdb_ci_registry

        if isinstance(statement, str):
            code = compile(statement, SCRIPT_FILE_NAME, 'exec')
        else:
            code = statement

        self.thread = threading.Thread(
            target=exec_with_trace,
            args=(code, trace, self._done),
            daemon=True
        )
        self.thread.start()

    def _done(self, exception=None):
        # to be called at the end of exec_with_trace()
        next_state = Finished(thread=self.thread, exception=exception)
        self.finished(next_state)

    def send_pdb_command(self, thread_asynctask_id, command):
        pdb_ci = self.pdb_ci_registry.get_ci(thread_asynctask_id)
        pdb_ci.send_pdb_command(command)


class Finished(State):
    """The state "finished", the script execution has finished

    Parameters
    ----------
    thread : object
        The object of the thread in which the script was executed.
        This thread is to be joined.
    exception : exception or None
        The execution raised in the script execution if any. Otherwise
        None
    """

    name = "finished"
    def __init__(self, thread, exception):
        self.thread = thread
        self.exception = exception
    async def wait(self):
        if self.thread:
            await self._join(self.thread)
    async def _join(self, thread):
        try:
            await asyncio.to_thread(thread.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, thread.join)

##__________________________________________________________________||
