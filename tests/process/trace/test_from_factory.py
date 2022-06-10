import pytest

from nextline.process.trace import TraceFromFactory

from .funcs import TraceSummary

from . import module_a


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
    yield f


@pytest.fixture(params=[set(), {module_a.__name__}])
def modules_to_skip(request):
    y = request.param
    yield y


@pytest.fixture()
def target_trace_func(mock_factory):
    y = TraceFromFactory(factory=mock_factory)
    yield y


@pytest.fixture()
def mock_factory(probe_trace_func):
    return lambda: probe_trace_func


@pytest.fixture()
def thread():
    yield False
