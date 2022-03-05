import pytest
from unittest.mock import Mock

from typing import Callable, Union, Any, Set

from nextline.call import call_with_trace
from nextline.types import TraceFunc

from .funcs import summarize_trace_calls


@pytest.fixture()
def target(
    wrap_target_trace_func: Union[TraceFunc, Mock],
    modules_in_summary: Union[Set[str], None],
    run_target,
):
    _ = run_target
    y = summarize_trace_calls(
        wrap_target_trace_func, modules=modules_in_summary  # type: ignore
    )
    yield y


@pytest.fixture()
def probe(
    probe_trace_func: Mock,
    modules_in_summary: Union[Set[str], None],
    run_target,
):
    _ = run_target
    y = summarize_trace_calls(probe_trace_func, modules=modules_in_summary)
    yield y


@pytest.fixture()
def ref(
    ref_trace_func: Mock,
    modules_in_summary: Union[Set[str], None],
    run_ref,
):
    _ = run_ref
    y = summarize_trace_calls(ref_trace_func, modules=modules_in_summary)
    yield y


@pytest.fixture()
def modules_in_summary():
    yield None


@pytest.fixture()
def run_target(
    func: Callable[[], Any],
    wrap_target_trace_func: Union[TraceFunc, Mock],
    thread: bool,
):
    call_with_trace(func=func, trace=wrap_target_trace_func, thread=thread)
    yield


@pytest.fixture()
def run_ref(
    func: Callable[[], Any],
    ref_trace_func: Union[TraceFunc, Mock],
    thread: bool,
):
    call_with_trace(func=func, trace=ref_trace_func, thread=thread)
    yield


@pytest.fixture()
def wrap_target_trace_func(target_trace_func: TraceFunc):
    wrap = Mock(wraps=target_trace_func)

    def side_effect(*a, **k):
        local_trace_func = target_trace_func(*a, **k)
        if local_trace_func is target_trace_func:
            return wrap
        return local_trace_func

    wrap.side_effect = side_effect
    yield wrap


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
