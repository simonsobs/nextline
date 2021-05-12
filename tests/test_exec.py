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

##__________________________________________________________________||
def test_simple(trace):
    done = Mock()
    code = compile(SOURCE, '<string>', 'exec')

    exec_with_trace(code=code, trace=trace, done=done)

    assert 3 == trace.call_count
    # print(trace.call_args_list)

    assert [call()] == done.call_args_list

##__________________________________________________________________||
