import sys
import asyncio
import threading
import queue
import linecache

from .trace import Trace, State
from .queuedist import QueueDist

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.trace = None
        self.state = None
        self.global_state = "initialized"

        self.queue_global_state = QueueDist()
        self.queue_global_state.put(self.global_state)

        self.state = State()

    def run(self):
        if __name__ in self.breaks:
            self.breaks[__name__].append('<module>')
        else:
            self.breaks[__name__] = ['<module>']
        self.trace = Trace(state=self.state, breaks=self.breaks, statement=self.statement)
        self.pdb_ci_registry = self.trace.pdb_ci_registry

        self.t = threading.Thread(target=self._execute_statement_with_trace, daemon=True)
        self.t.start()

    def _execute_statement_with_trace(self):
        if isinstance(self.statement, str):
            cmd = compile(self.statement, '<string>', 'exec')
        else:
            cmd = self.statement
        self.global_state = "running"
        self.queue_global_state.put(self.global_state)
        trace_org = sys.gettrace()
        threading.settrace(self.trace)
        sys.settrace(self.trace)
        try:
            exec(cmd)
        finally:
            sys.settrace(trace_org)
            threading.settrace(trace_org)
        self.global_state = "finished"
        self.queue_global_state.put(self.global_state)

    async def subscribe_global_state(self):
        async for y in self.queue_global_state.subscribe():
            yield y

    async def subscribe_thread_asynctask_ids(self):
        async for y in self.state.subscribe_thread_asynctask_ids():
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        async for y in self.state.subscribe_thread_asynctask_state(thread_asynctask_id):
            yield y

    def get_source(self, file_name=None):
        if not file_name or file_name == '<string>':
            return self.statement.split('\n')
        return [l.rstrip() for l in linecache.getlines(file_name)]

    def send_pdb_command(self, thread_asynctask_id, command):
        pdb_ci = self.pdb_ci_registry.get_ci(thread_asynctask_id)
        pdb_ci.send_pdb_command(command)

    async def wait(self):
        try:
            await asyncio.to_thread(self.t.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.t.join)

        await self.queue_global_state.close()
        await self.state.close()

    @property
    def pdb_cis(self):
        return self.pdb_ci_registry.pdb_cis

    def nthreads(self):
        if self.state is None:
            return 0
        return self.state.nthreads

##__________________________________________________________________||
