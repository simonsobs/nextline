import sys
import asyncio
import threading
import queue

import janus

from .trace import Trace

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.condition = threading.Condition()
        self.trace = None
        self.state = None
        self.status = "initialized"

        from . import ThreadSafeAsyncioEvent
        self.event = ThreadSafeAsyncioEvent()


    def run(self):
        if __name__ in self.breaks:
            self.breaks[__name__].append('<module>')
        else:
            self.breaks[__name__] = ['<module>']
        self.trace = Trace(breaks=self.breaks, statement=self.statement, event=self.event)
        self.state = self.trace.state
        self.pdb_ci_registry = self.trace.pdb_ci_registry

        self.t = threading.Thread(target=self._execute_statement_with_trace, daemon=True)
        self.t.start()

    def _execute_statement_with_trace(self):
        if isinstance(self.statement, str):
            cmd = compile(self.statement, '<string>', 'exec')
        else:
            cmd = self.statement
        self.status = "running"
        trace_org = sys.gettrace()
        threading.settrace(self.trace)
        sys.settrace(self.trace)
        try:
            exec(cmd)
        finally:
            sys.settrace(trace_org)
            threading.settrace(trace_org)
        self.status = "finished"

    async def nextline_generator(self):
        while True:
            yield self
            self.event.clear()
            await self.event.wait()

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
