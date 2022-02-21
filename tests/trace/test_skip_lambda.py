import pytest
from unittest.mock import Mock

from nextline.trace import TraceSkipLambda

from .funcs import TraceSummaryType

from . import module_a


def test_one(
    target: TraceSummaryType,
    probe: TraceSummaryType,
    ref: TraceSummaryType,
):
    assert ref.call.func
    assert ref.return_.func
    assert ref.call.func == target.call.func
    assert not target.return_.func
    assert ref.call.func - {"<lambda>"} == probe.call.func
    assert ref.call.func - {"<lambda>"} == probe.return_.func


def f():
    module_a.func_a()


def g():
    (lambda: module_a.func_a())()


@pytest.fixture(params=[f, g, lambda: module_a.func_a()])
def func(request):
    yield request.param


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock):
    y = TraceSkipLambda(trace=probe_trace_func)
    yield y


@pytest.fixture()
def thread():
    yield False
