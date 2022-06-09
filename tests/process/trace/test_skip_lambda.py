import pytest
from unittest.mock import Mock

from nextline.process.trace import TraceSkipLambda

from .funcs import TraceSummary

from . import module_a


def test_one(target: TraceSummary, probe: TraceSummary, ref: TraceSummary):
    assert ref.call.func
    assert ref.return_.func
    assert ref.call.func == target.call.func
    assert not target.return_.func
    assert set(ref.call.func) - {"<lambda>"} == set(probe.call.func)
    assert set(ref.return_.func) - {"<lambda>"} == set(probe.return_.func)


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
