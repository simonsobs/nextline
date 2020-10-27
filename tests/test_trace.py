import sys
import threading
import asyncio
import janus
from functools import partial

from nextline.trace import Trace, LocalTrace, create_thread_task_id

import pytest
from unittest.mock import Mock

##__________________________________________________________________||
def subject():
    return

def control():
    pass

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_simple():

    thread_task_id = create_thread_task_id()
    local_queues = (Mock(), Mock())
    q_in, q_out = local_queues
    q_in.sync_q.get.return_value = 'next'

    queue_trace_to_control = janus.Queue()
    local_queue_dict = { thread_task_id: local_queues }
    condition = threading.Condition()
    breaks = { __name__: ['subject'] }
    trace = Trace(queue_trace_to_control, local_queue_dict, condition, breaks)

    trace_org = sys.gettrace()
    sys.settrace(trace)
    subject()
    sys.settrace(trace_org)
    print(q_out.sync_q.put.call_args_list)

##__________________________________________________________________||
def call_with_trace(func, trace):
    module_name = func.__module__
    func_name = func.__name__

    def trace_(frame, event, arg):
        if module_name != frame.f_globals.get('__name__'):
            return None
        if func_name != frame.f_code.co_name:
            return None
        return trace(frame, event, arg)

    trace_org = sys.gettrace()
    sys.settrace(trace_)
    func()
    sys.settrace(trace_org)

@pytest.mark.asyncio
async def test_local():
    local_queues = (janus.Queue(), janus.Queue())
    thread_task_id = create_thread_task_id()
    q_in, q_out = local_queues
    localtrace = LocalTrace(local_queues, thread_task_id)
    t = threading.Thread(target=call_with_trace, args=(subject, localtrace))
    t.start()

    print()
    print(await q_out.async_q.get())
    await q_in.async_q.put('next')
    print(await q_out.async_q.get())
    await q_in.async_q.put('next')
    print(await q_out.async_q.get())
    await q_in.async_q.put('next')

    t.join()
    q_in.close()
    q_out.close()
    await asyncio.gather(q_in.wait_closed(), q_out.wait_closed())

##__________________________________________________________________||
