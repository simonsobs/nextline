import sys
import asyncio
import threading
import queue
import linecache

from .registry import Registry
from .trace import Trace
from .utils import QueueDist
from .exec_ import exec_with_trace

##__________________________________________________________________||
class Nextline:
    """Nextline allows line-by-line execution of concurrent Python scripts

    Nextline supports concurrency with threading and asyncio. It uses
    an instance of Pdb for each thread and async task.

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
        self._state = Initialized(nextline=self)
        self._queue_state_name.put(self._state.name)

    @property
    def global_state(self) -> str:
        """state, e.g., "initialized", "running", "finished"
        """
        return self._state.name

    def run(self):
        """run the script
        """
        self._state = self._state.run(statement=self.statement, finished=self._finished)
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

    async def wait(self):
        await self._state.wait()
        await self.registry.close()
        await self._queue_state_name.close()

    async def subscribe_global_state(self):
        async for y in self._queue_state_name.subscribe():
            yield y

    async def subscribe_thread_asynctask_ids(self):
        async for y in self.registry.subscribe_thread_asynctask_ids():
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        async for y in self.registry.subscribe_thread_asynctask_state(thread_asynctask_id):
            yield y

    def send_pdb_command(self, thread_asynctask_id, command):
        self._state.send_pdb_command(thread_asynctask_id, command)

    def get_source(self, file_name=None):
        if not file_name or file_name == '<string>':
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
    """The base class of the states
    """
    def __init__(self, nextline):
        self.nextline = nextline
        self.thread = None

    def run(self, *_, **__):
        return self

    async def wait(self):
        pass

    def send_pdb_command(self, thread_asynctask_id, command):
        pass

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

class Initialized(State):
    name = "initialized"
    def __init__(self, nextline):
        super().__init__(nextline)
    def run(self, statement, finished):
        return Running(nextline=self.nextline, statement=statement, finished=finished)

class Running(State):
    name = "running"

    def __init__(self, nextline, statement, finished):
        super().__init__(nextline)

        self.finished = finished

        trace = Trace(registry=nextline.registry)
        self.pdb_ci_registry = trace.pdb_ci_registry

        if isinstance(statement, str):
            code = compile(statement, '<string>', 'exec')
        else:
            code = statement

        self.thread = threading.Thread(
            target=exec_with_trace,
            args=(code, trace, self._done),
            daemon=True
        )
        self.thread.start()

    def _done(self, exception=None):
        # to be called at the end of self._exec()
        next_state = Finished(nextline=self.nextline, thread=self.thread)
        self.finished(next_state)

    def send_pdb_command(self, thread_asynctask_id, command):
        pdb_ci = self.pdb_ci_registry.get_ci(thread_asynctask_id)
        pdb_ci.send_pdb_command(command)


class Finished(State):
    name = "finished"
    def __init__(self, nextline, thread):
        super().__init__(nextline)
        self.thread = thread

##__________________________________________________________________||
