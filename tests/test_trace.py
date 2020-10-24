import sys
import threading
import asyncio
import janus

from nextline.trace import Trace, create_thread_task_id

import pytest
from unittest.mock import Mock



##__________________________________________________________________||
def subject():
    return

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_simple():

    thread_task_id = create_thread_task_id()
    local_queues = (Mock(), Mock())
    q_in, q_out = local_queues
    q_in.sync_q.get.return_value = None

    global_queue = janus.Queue()
    local_queue_dict = { thread_task_id: local_queues }
    condition = threading.Condition()
    breaks = { __name__: ['subject'] }
    trace = Trace(global_queue, local_queue_dict, condition, breaks)

    sys.settrace(trace)
    subject()
    sys.settrace(None)
    print(q_out.sync_q.put.call_args_list)

##__________________________________________________________________||
