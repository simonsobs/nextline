import sys
import asyncio
import threading
import queue
import linecache

from .registry import Registry
from .trace import Trace
from .utils import QueueDist

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement):
        self.statement = statement
        self.queue_global_state = QueueDist()
        self.registry = Registry()
        self.state = Initialized(nextline=self)

    @property
    def global_state(self):
        return self.state.name

    def run(self):
        self.state = self.state.run(statement=self.statement)

    def finished(self, t):
        self.state = self.state.finished(t)

    async def subscribe_global_state(self):
        async for y in self.queue_global_state.subscribe():
            yield y

    async def subscribe_thread_asynctask_ids(self):
        async for y in self.registry.subscribe_thread_asynctask_ids():
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        async for y in self.registry.subscribe_thread_asynctask_state(thread_asynctask_id):
            yield y

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

    def send_pdb_command(self, thread_asynctask_id, command):
        self.state.send_pdb_command(thread_asynctask_id, command)

    async def wait(self):
        async for s in self.subscribe_global_state():
            if s == 'finished':
                break
        await self.state.wait()
        await self.registry.close()
        await self.queue_global_state.close()

##__________________________________________________________________||
class State:
    """The base class of the states
    """
    def __init__(self, nextline):
        self.nextline = nextline
        self.nextline.queue_global_state.put(self.name)
    def run(self, statement):
        return self
    async def wait(self):
        pass
    def finished(self, t):
        return self
    def send_pdb_command(self, thread_asynctask_id, command):
        pass

class Initialized(State):
    name = "initialized"
    def __init__(self, nextline):
        super().__init__(nextline)
    def run(self, statement):
        return Running(nextline=self.nextline, statement=statement)

class Running(State):
    name = "running"

    def __init__(self, nextline, statement):
        super().__init__(nextline)

        self.loop = asyncio.get_running_loop()
        self.statement = statement
        self.registry = nextline.registry
        self.trace = Trace(registry=self.registry)
        self.pdb_ci_registry = self.trace.pdb_ci_registry

        if isinstance(self.statement, str):
            cmd = compile(self.statement, '<string>', 'exec')
        else:
            cmd = self.statement
        self.t = threading.Thread(target=self._execute_statement_with_trace, args=(cmd, ), daemon=True)
        self.t.start()

    def _execute_statement_with_trace(self, cmd):
        trace_org = sys.gettrace()
        threading.settrace(self.trace)
        sys.settrace(self.trace)
        try:
            exec(cmd)
        except BaseException as e:
            print(e)
            raise
        finally:
            sys.settrace(trace_org)
            threading.settrace(trace_org)

        self.nextline.finished(self.t)

    def finished(self, t):
        return Finished(nextline=self.nextline, t=t)

    def send_pdb_command(self, thread_asynctask_id, command):
        pdb_ci = self.pdb_ci_registry.get_ci(thread_asynctask_id)
        pdb_ci.send_pdb_command(command)


class Finished(State):
    name = "finished"
    def __init__(self, nextline, t):
        super().__init__(nextline)
        self.t = t
    async def wait(self):
        try:
            await asyncio.to_thread(self.t.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.t.join)

##__________________________________________________________________||
