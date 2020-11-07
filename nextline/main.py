import sys
import asyncio
import threading
import queue

import janus

from .trace import Trace
from .control import ThreadAsyncTaskRegistry

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.condition = threading.Condition()
        self.thread_asynctask_regsitry = None
        self.status = "initialized"

    def run(self):
        self.thread_asynctask_regsitry = ThreadAsyncTaskRegistry()
        self.trace = Trace(self.thread_asynctask_regsitry, self.breaks)
        self.t = threading.Thread(target=self._execute_statement_with_trace)
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

    def nthreads(self):
        return self.thread_asynctask_regsitry.nthreads()

##__________________________________________________________________||
