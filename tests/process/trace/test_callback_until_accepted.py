from unittest.mock import Mock

import pytest

from nextline.process.trace import TraceCallbackUntilAccepted

from . import module_a
from .funcs import TraceSummary, summarize_trace_calls


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    callback: Mock,
    callback_return: bool,
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call == target.call
    assert not target.return_.module
    assert ref == probe

    callback_summary = summarize_trace_calls(callback)
    if callback_return:
        assert [f1.__module__] == callback_summary.call.module
        assert [f1.__name__] == callback_summary.call.func
        assert not callback_summary.line.module
        assert not callback_summary.return_.module
    else:
        assert probe == callback_summary


def f1():
    module_a.func_a()


@pytest.fixture()
def func():
    return f1


@pytest.fixture(params=[True, False])
def callback_return(request):
    return request.param


@pytest.fixture
def callback(callback_return: bool):
    y = Mock(return_value=callback_return)
    return y


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, callback: Mock):
    y = TraceCallbackUntilAccepted(trace=probe_trace_func, callback=callback)
    return y
