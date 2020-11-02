import sys
import asyncio
import threading
import queue

import janus

from .trace import Trace
from .control import Control

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.condition = threading.Condition()
        self.control = None
        self.finished = False

    def run(self):
        self.control = Control()
        self.trace = Trace(self.control, self.breaks)
        self.t = threading.Thread(target=self._execute_statement_with_trace)
        self.t.start()

    def _execute_statement_with_trace(self):
        if isinstance(self.statement, str):
            cmd = compile(self.statement, '<string>', 'exec')
        else:
            cmd = self.statement
        self.finished = False
        trace_org = sys.gettrace()
        threading.settrace(self.trace)
        sys.settrace(self.trace)
        try:
            exec(cmd)
        finally:
            sys.settrace(trace_org)
            threading.settrace(trace_org)
        self.finished = True

    async def wait(self):
        self.control.end()
        await asyncio.to_thread(self.t.join)

    def nthreads(self):
        return self.control.nthreads()

##__________________________________________________________________||
