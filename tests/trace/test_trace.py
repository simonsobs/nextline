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
    assert 2 == MockPdbProxy().call_count


##__________________________________________________________________||
params = [
    pytest.param(set(), id="empty"),
    pytest.param({"some_module"}, id="one-value"),
    pytest.param(None, id="none"),
    pytest.param(False, id="default"),
]


@pytest.mark.parametrize("modules_to_trace", params)
@pytest.mark.asyncio
async def test_modules_to_trace(MockPdbProxy, modules_to_trace):
    from . import module_a
    from . import module_b

    registry = Registry()

    kwargs = {}
    if modules_to_trace is not False:
        kwargs["modules_to_trace"] = modules_to_trace

    trace = Trace(registry, **kwargs)

    trace_org = sys.gettrace()
    sys.settrace(trace)
    module_a.func()
    sys.settrace(trace_org)

    assert modules_to_trace is not trace.modules_to_trace
    if modules_to_trace:
        assert modules_to_trace <= trace.modules_to_trace

    traced_moduled = {
        c.args[0].f_globals.get("__name__")
        for c in MockPdbProxy().call_args_list
    }

    # module_b is traced but not in the set modules_to_trace
    assert module_a.__name__ in trace.modules_to_trace
    assert {module_a.__name__, module_b.__name__} == traced_moduled


@pytest.mark.asyncio
async def test_modules_to_trace_partial(MockPdbProxy):
    """
    This test investigate what happens if a partial is the first
    function to be called. The module_a still appears to be the first
    module and added to the set modules_to_trace. It is not clear why
    partial.__call__() is not traced.
    """
    from functools import partial
    from . import module_a
    from . import module_b

    registry = Registry()

    trace = Trace(registry)

    func = partial(module_a.func)

    trace_org = sys.gettrace()
    sys.settrace(trace)
    func()
    sys.settrace(trace_org)

    traced_moduled = {
        c.args[0].f_globals.get("__name__")
        for c in MockPdbProxy().call_args_list
    }

    # module_b is traced but not in the set modules_to_trace
    assert module_a.__name__ in trace.modules_to_trace
    assert {module_a.__name__, module_b.__name__} == traced_moduled


##__________________________________________________________________||
@pytest.mark.skip(reason="no need to pass")
@pytest.mark.asyncio
async def test_return(MockPdbProxy):
    """test if correct trace function is returned"""
    registry = Registry()
    trace = Trace(registry, modules_to_trace={})
    frame = Mock()
    assert trace(frame, "call", None) is MockPdbProxy()()
    assert trace(frame, "line", None) is MockPdbProxy()()

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
        call(frame, "call", None),
        call(frame, "line", None),
    ] == MockPdbProxy().call_args_list


##__________________________________________________________________||
