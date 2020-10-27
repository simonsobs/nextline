import threading
import asyncio
import janus

import pytest
from unittest.mock import Mock

from nextline.control import Control

##__________________________________________________________________||
async def communicate(queue_trace_to_control):
    await asyncio.sleep(0.01)
    key = 'key'
    await queue_trace_to_control.async_q.put(key)
    await queue_trace_to_control.async_q.put(None)

@pytest.mark.asyncio
async def test_simple():
    queue_trace_to_control = janus.Queue()
    local_queue_dict = { }
    condition = threading.Condition()
    control = Control(queue_trace_to_control, local_queue_dict, condition)
    control.run()
    com = communicate(queue_trace_to_control)
    await asyncio.gather(control.wait(), com)
    assert {'key'} == control.thread_task_ids
    assert 1 == len(control.local_control_tasks)

##__________________________________________________________________||
