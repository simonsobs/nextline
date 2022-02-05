import sys

import pytest
from unittest.mock import Mock, call

from nextline.trace import Trace
from nextline.utils import Registry
from nextline.pdb.proxy import PdbProxy


##__________________________________________________________________||
@pytest.fixture()
def MockPdbProxy(monkeypatch):
    mock_instance = Mock(spec=PdbProxy)
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr("nextline.trace.PdbProxy", mock_class)
    yield mock_class


##__________________________________________________________________||
def f():
    pass


def subject():
    f()
    return


@pytest.mark.asyncio
async def test_sys_settrace(MockPdbProxy):
    """test with actual sys.settrace()"""
    registry = Registry()
    trace = Trace(registry, modules_to_trace={})

    trace_org = sys.gettrace()
    sys.settrace(trace)
    subject()
    sys.settrace(trace_org)

    assert 1 == MockPdbProxy.call_count
    assert 2 == MockPdbProxy().trace_func.call_count


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_return(MockPdbProxy):
    """test if correct trace function is returned"""
    registry = Registry()
    trace = Trace(registry, modules_to_trace={})
    frame = Mock()
    assert trace(frame, "call", None) is MockPdbProxy().trace_func()
    assert trace(frame, "line", None) is MockPdbProxy().trace_func()

    assert 1 + 2 == MockPdbProxy.call_count
    # once in trace(), twice in the above lines in the test


@pytest.mark.asyncio
async def test_args(MockPdbProxy):
    """test if arguments are properly propagated to the proxy"""
    registry = Registry()
    trace = Trace(registry, modules_to_trace={})
    frame = Mock()
    trace(frame, "call", None)
    trace(frame, "line", None)
    assert [
        call.trace_func(frame, "call", None),
        call.trace_func(frame, "line", None),
    ] == MockPdbProxy().method_calls


##__________________________________________________________________||
