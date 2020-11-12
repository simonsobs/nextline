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

    def run(self):
        if __name__ in self.breaks:
            self.breaks[__name__].append('<module>')
        else:
            self.breaks[__name__] = ['<module>']
        self.trace = Trace(self.statement, self.breaks)
        self.state = self.trace.state
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

    async def wait(self):
        await asyncio.to_thread(self.t.join)

    @property
    def pdb_cis(self):
        return self.trace.pdb_ci_registry.pdb_cis

    def nthreads(self):
        if self.state is None:
            return 0
        return self.state.nthreads()

##__________________________________________________________________||
