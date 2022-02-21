import pytest
from unittest.mock import Mock

from typing import Callable, Union, Any, Set

from nextline.call import call_with_trace
from nextline.trace import TraceSkipModule
from nextline.types import TraceFunc

from .funcs import summarize_trace_calls, TraceSummaryType

from . import module_a


def test_one(
    target: TraceSummaryType,
    probe: TraceSummaryType,
    ref: TraceSummaryType,
    modules_to_skip: Set[str],
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call.module == target.call.module
    assert not target.return_.module
    assert ref.call.module - modules_to_skip == probe.call.module
    assert ref.call.module - modules_to_skip == probe.return_.module


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
def target_trace_func(probe_trace_func: Mock, modules_to_skip: Set[str]):
    y = TraceSkipModule(
        trace=probe_trace_func,
        skip=modules_to_skip,
    )
    yield y


@pytest.fixture()
def thread():
    yield False


@pytest.fixture()
def target(wrap_target_trace_func: Union[TraceFunc, Mock], run_target):
    _ = run_target
    y = summarize_trace_calls(wrap_target_trace_func)
    yield y


@pytest.fixture()
def probe(probe_trace_func: Mock, run_target):
    _ = run_target
    y = summarize_trace_calls(probe_trace_func)
    yield y


@pytest.fixture()
def ref(ref_trace_func: Mock, run_ref):
    _ = run_ref
    y = summarize_trace_calls(ref_trace_func)
    yield y


@pytest.fixture()
def run_target(
    func: Callable[[], Any],
    wrap_target_trace_func: Union[TraceFunc, Mock],
    thread: bool,
):
    call_with_trace(func=func, trace=wrap_target_trace_func, thread=thread)
    yield


@pytest.fixture()
def run_ref(func: Callable[[], Any], ref_trace_func: Union[TraceFunc, Mock]):
    call_with_trace(func=func, trace=ref_trace_func, thread=False)
    yield


@pytest.fixture()
def wrap_target_trace_func(target_trace_func: TraceFunc):
    y = Mock(wraps=target_trace_func)
    yield y


@pytest.fixture()
def probe_trace_func():
    y = Mock()
    y.return_value = y
    yield y


@pytest.fixture()
def ref_trace_func():
    y = Mock()
    y.return_value = y
    yield y
