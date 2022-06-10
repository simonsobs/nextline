import sys
from threading import Thread
import traceback

import pytest
from unittest.mock import Mock

from nextline.process.call import call_with_trace


@pytest.fixture()
def trace():
    f = Mock()
    f.return_value = f
    yield f


def test_simple(trace):
    def func():
        x = 123
        return x

    trace_org = sys.gettrace()
    ret, exc = call_with_trace(func, trace=trace)
    assert trace_org == sys.gettrace()
    assert 123 == ret
    assert exc is None
    # print(trace.call_args_list)
    assert 4 == trace.call_count  # "call", "line", "line", "return"


class MockError(Exception):
    pass


def test_raise(trace):
    def func():
        raise MockError()

    trace_org = sys.gettrace()

    ret, exc = call_with_trace(func, trace=trace)

    assert trace_org == sys.gettrace()

    assert ret is None
    assert isinstance(exc, MockError)

    assert 4 == trace.call_count  # "call", "line", "exception", "return"

    # assert the frame of call_with_trace() is removed
    formatted = traceback.format_exception(type(exc), exc, exc.__traceback__)
    assert len(formatted) == 3


@pytest.mark.parametrize("thread", [True, False])
def test_threading(trace, thread):
    def f1():
        return

    def func():
        t1 = Thread(target=f1)
        t1.start()
        t1.join()

    trace_org = sys.gettrace()

    call_with_trace(func, trace=trace, thread=thread)

    assert trace_org == sys.gettrace()

    traced = {
        (
            c.args[0].f_globals.get("__name__"),
            c.args[0].f_code.co_name,
        )
        for c in trace.call_args_list
    }
    # set: {(<module name>, <func name>)}

    expected_subset = {(func.__module__, func.__name__)}

    if thread:
        expected_subset.update({(f1.__module__, f1.__name__)})

    assert expected_subset <= traced
