import sys
import asyncio
import threading

import janus

from .trace import Trace
from .control import Control

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.futures = set()
        self.condition = threading.Condition()
        self.control = None
        self.global_queue = None # create in run(), where a loop is running.
        self.local_queue_dict = {}

    def run(self):
        self.global_queue = janus.Queue()
        loop = asyncio.get_running_loop()
        self.futures.add(loop.run_in_executor(None, self._execute_statement_with_trace))
        self.control = Control(self.global_queue, self.local_queue_dict, self.condition)
        self.futures.add(asyncio.create_task(self.control.run()))

    def _execute_statement_with_trace(self):
        if isinstance(self.statement, str):
            cmd = compile(self.statement, '<string>', 'exec')
        else:
            cmd = self.statement
        trace = Trace(self.global_queue, self.local_queue_dict, self.condition, self.breaks)
        trace_org = sys.gettrace()
        threading.settrace(trace)
        sys.settrace(trace)
        try:
            exec(cmd)
        finally:
            sys.settrace(trace_org)
            threading.settrace(trace_org)
            self.global_queue.sync_q.put(None)

    async def wait(self):
        await asyncio.gather(*self.futures)
        self.futures.clear()

    async def nthreads(self):
        with self.condition:
            return len({i for i, _ in self.control.thread_task_ids})

##__________________________________________________________________||
