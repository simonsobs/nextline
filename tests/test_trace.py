import sys
import queue

from nextline.trace import Trace, LocalTrace, create_thread_task_id

import pytest
from unittest.mock import Mock

##__________________________________________________________________||
def subject():
    return

##__________________________________________________________________||
@pytest.fixture()
def mock_queue(monkeypatch):
    y = Mock()
    monkeypatch.setattr("nextline.trace.queue", y)
    yield y

def test_trace(mock_queue):

    mock_queue.Queue().get.return_value = 'next'

    queue_to_control = Mock()
    queue_from_control = Mock()
    breaks = { __name__: ['subject'] }
    trace = Trace(queue_to_control, queue_from_control, breaks)

    trace_org = sys.gettrace()
    sys.settrace(trace)
    subject()
    sys.settrace(trace_org)

    assert 3 == len(mock_queue.Queue().put.call_args_list)
    assert 1 == len(queue_to_control.put.call_args_list)

##__________________________________________________________________||
def test_local_trace():
    local_queues = (Mock(), Mock())
    q_in, q_out = local_queues
    q_in.get.return_value = 'next'

    local_trace = LocalTrace(local_queues)

    trace_org = sys.gettrace()
    sys.settrace(local_trace)
    subject()
    sys.settrace(trace_org)

    assert 3 == len(q_out.put.call_args_list)

##__________________________________________________________________||
