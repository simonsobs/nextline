import sys

import pytest
from unittest.mock import Mock, call, sentinel

from nextline.trace import Trace, compose_thread_asynctask_id
from nextline.pdb.proxy import PdbProxy

##__________________________________________________________________||
@pytest.fixture()
def MockPdbProxy(monkeypatch):
    mock_instance = Mock(spec=PdbProxy)
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr('nextline.trace.PdbProxy', mock_class)
    yield mock_class

##__________________________________________________________________||
def f():
    pass

def subject():
    f()
    return

def test_sys_settrace(MockPdbProxy, snapshot):
    """test with actual sys.settrace()
    """
    trace = Trace()

    trace_org = sys.gettrace()
    sys.settrace(trace)
    subject()
    sys.settrace(trace_org)

    id_ = compose_thread_asynctask_id()

    assert 1 == MockPdbProxy.call_count
    assert 1 == MockPdbProxy().trace_func_init.call_count
    assert 1 == MockPdbProxy().trace_func.call_count

##__________________________________________________________________||
def test_return(MockPdbProxy):
    """test if correct trace functions are returned
    """
    trace = Trace()
    assert trace(sentinel.frame, 'call', None) is MockPdbProxy().trace_func_init()
    assert trace(sentinel.frame, 'line', None) is MockPdbProxy().trace_func()

def test_args(MockPdbProxy, snapshot):
    """test if arguments are properly propagated to the proxy
    """
    trace = Trace()
    trace(sentinel.frame, 'call', None)
    trace(sentinel.frame, 'line', None)
    snapshot.assert_match(MockPdbProxy().method_calls)

##__________________________________________________________________||
