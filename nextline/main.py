import sys
import asyncio
import threading

from functools import partial

import janus

from .trace import Trace
from .control import Control

##__________________________________________________________________||
def exec_statement(cmd, breaks, jqueue, local_queue_dict, condition):
    if isinstance(cmd, str):
        cmd = compile(cmd, '<string>', 'exec')
    trace_func = Trace(jqueue, local_queue_dict, condition, breaks)
    threading.settrace(trace_func)
    sys.settrace(trace_func)
    try:
        exec(cmd)
    finally:
        sys.settrace(None)
        threading.settrace(None)
        jqueue.sync_q.put(None)

##__________________________________________________________________||
class Nextline:
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.futures = set()
        self.condition = threading.Condition()
        self.control = None

    def run(self):
        global_queue = janus.Queue()
        local_queue_dict = {}
        exec_ = partial(exec_statement, self.statement, self.breaks, global_queue, local_queue_dict, self.condition)
        loop = asyncio.get_running_loop()
        self.futures.add(loop.run_in_executor(None, exec_))
        self.control = Control(global_queue, local_queue_dict, self.condition)
        self.futures.add(asyncio.create_task(self.control.run()))

    async def wait(self):
        await asyncio.gather(*self.futures)
        self.futures.clear()

    async def nthreads(self):
        with self.condition:
            return len({i for i, _ in self.control.thread_task_ids})

##__________________________________________________________________||
