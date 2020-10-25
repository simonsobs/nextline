import threading
import asyncio
import janus

import pytest
from unittest.mock import Mock

from nextline.control import Control

##__________________________________________________________________||
async def communicate(global_queue):
    await asyncio.sleep(0.01)
    key = 'key'
    await global_queue.async_q.put(key)
    await global_queue.async_q.put(None)

@pytest.mark.asyncio
async def test_simple():
    global_queue = janus.Queue()
    local_queue_dict = { }
    condition = threading.Condition()
    control = Control(global_queue, local_queue_dict, condition)
    run = control.run()
    com = communicate(global_queue)
    await asyncio.wait([run, com])
    assert {'key'} == control.thread_task_ids
    assert 1 == len(control.local_control_tasks)

##__________________________________________________________________||
