from threading import Thread
import pytest
from unittest.mock import Mock, call

from nextline.call import call_with_trace


##__________________________________________________________________||
@pytest.fixture()
def trace():
    f = Mock()
    f.return_value = f
    yield f


##__________________________________________________________________||
def test_simple(trace):
    def func():
        x = 123
        return x

    done = Mock()
    call_with_trace(func, trace=trace, done=done)
    # print(trace.call_args_list)
    assert 4 == trace.call_count  # "call", "line", "line", "return"
    assert [call(123, None)] == done.call_args_list


##__________________________________________________________________||
def test_raise(trace):
    def func():
        raise Exception("foo", "bar")

    done = Mock()

    call_with_trace(func, trace=trace, done=done)

    assert 4 == trace.call_count  # "call", "line", "exception", "return"

    # print(trace.call_args_list)

    assert 1 == done.call_count
    ret, exc = done.call_args.args
    assert ret is None
    assert isinstance(exc, Exception)
    assert ("foo", "bar") == exc.args
    with pytest.raises(Exception):
        raise exc


##__________________________________________________________________||
def test_threading(trace):
    def f1():
        return

    def func():
        t1 = Thread(target=f1)
        t1.start()
        t1.join()

    done = Mock()
    call_with_trace(func, trace=trace, done=done)
    # print(trace.call_args_list)

    traced = {
        (
            c.args[0].f_globals.get("__name__"),
            c.args[0].f_code.co_name,
        )
        for c in trace.call_args_list
    }
    # set: {(<module name>, <func name>)}

    expected_subset = {
        (f1.__module__, f1.__name__),
        (func.__module__, func.__name__),
    }

    assert expected_subset <= traced

    assert [call(None, None)] == done.call_args_list


##__________________________________________________________________||
