import sys
import asyncio
import threading
import queue
import linecache

import janus

from .trace import Trace, State

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.condition = threading.Condition()
        self.trace = None
        self.state = None
        self.global_state = "initialized"

        from . import ThreadSafeAsyncioEvent
        self.event_global_state = ThreadSafeAsyncioEvent()

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
        self.event_global_state.set()
        trace_org = sys.gettrace()
        threading.settrace(self.trace)
        sys.settrace(self.trace)
        try:
            exec(cmd)
        finally:
            sys.settrace(trace_org)
            threading.settrace(trace_org)
        self.global_state = "finished"
        self.event_global_state.set()

    async def global_state_generator(self):
        while True:
            yield self.global_state
            self.event_global_state.clear()
            await self.event_global_state.wait()

    async def thread_task_ids_generator(self):
        event = self.state.event_thread_task_ids
        while True:
            yield self.state.thread_task_ids
            event.clear()
            await event.wait()

    async def nextline_generator(self):
        event = self.state.event
        while True:
            yield self
            event.clear()
            await event.wait()

    def get_source(self, file_name=None):
        if not file_name or file_name == '<string>':
            return self.statement.split('\n')
        return [l.rstrip() for l in linecache.getlines(file_name)]

    async def wait(self):
        try:
            await asyncio.to_thread(self.t.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.t.join)

    @property
    def pdb_cis(self):
        return self.pdb_ci_registry.pdb_cis

    def nthreads(self):
        if self.state is None:
            return 0
        return self.state.nthreads

##__________________________________________________________________||
