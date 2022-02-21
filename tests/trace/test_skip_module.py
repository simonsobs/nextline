import pytest
from unittest.mock import Mock

from typing import Union, Set

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


def func():
    module_a.func_a()


@pytest.fixture(params=[set(), {module_a.__name__}])
def modules_to_skip(request):
    y = request.param
    yield y


@pytest.fixture()
def target(target_trace_func: Union[TraceFunc, Mock], run_target):
    _ = run_target
    y = summarize_trace_calls(target_trace_func)
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
def run_target(target_trace_func: Union[TraceFunc, Mock]):
    call_with_trace(func=func, trace=target_trace_func, thread=False)
    yield


@pytest.fixture()
def run_ref(ref_trace_func: Union[TraceFunc, Mock]):
    call_with_trace(func=func, trace=ref_trace_func, thread=False)
    yield


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, modules_to_skip: Set[str]):
    y = TraceSkipModule(
        trace=probe_trace_func,
        skip=modules_to_skip,
    )
    y = Mock(wraps=y)
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
