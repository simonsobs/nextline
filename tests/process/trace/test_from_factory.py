import pytest

from nextline.process.trace import TraceFromFactory

from . import module_a
from .funcs import TraceSummary


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call == target.call
    assert not target.return_.module
    assert ref == probe


def f():
    module_a.func_a()


@pytest.fixture()
def func():
    return f


@pytest.fixture()
def target_trace_func(mock_factory):
    y = TraceFromFactory(factory=mock_factory)
    return y


@pytest.fixture()
def mock_factory(probe_trace_func):
    return lambda: probe_trace_func
