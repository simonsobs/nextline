import pytest
from unittest.mock import Mock, call

from nextline.exec_ import exec_with_trace

##__________________________________________________________________||
@pytest.fixture()
def trace():
    f = Mock()
    f.return_value = f
    yield f

##__________________________________________________________________||
SOURCE = """
x = 0
""".strip()

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()

##__________________________________________________________________||
def test_simple(trace):
    done = Mock()
    code = compile(SOURCE, '<string>', 'exec')

    exec_with_trace(code=code, trace=trace, done=done)

    assert 3 == trace.call_count
    # print(trace.call_args_list)

    assert [call(None, None)] == done.call_args_list

##__________________________________________________________________||
def test_raise(trace):
    done = Mock()
    code = compile(SOURCE_RAISE, '<string>', 'exec')

    exec_with_trace(code=code, trace=trace, done=done)

    assert 4 == trace.call_count
    # print(trace.call_args_list)

    assert 1 == done.call_count
    ret, exc = done.call_args.args
    assert ret is None
    assert isinstance(exc, Exception)
    assert ('foo', 'bar') == exc.args
    with pytest.raises(Exception):
        raise exc

##__________________________________________________________________||
