from __future__ import annotations

import pytest
from unittest.mock import Mock

from typing import TYPE_CHECKING, Callable, Any, Set

from nextline.process.call import call_with_trace

if TYPE_CHECKING:
    from sys import _TraceFunc as TraceFunc

from .funcs import TraceSummary, summarize_trace_calls


@pytest.fixture()
def target(
    wrap_target_trace_func: Mock,
    modules_in_summary: Set[str] | None,
    run_target,
) -> TraceSummary:
    _ = run_target
    y = summarize_trace_calls(
        wrap_target_trace_func, modules=modules_in_summary
    )
    return y


@pytest.fixture()
def probe(
    probe_trace_func: Mock,
    modules_in_summary: Set[str] | None,
    run_target,
) -> TraceSummary:
    _ = run_target
    y = summarize_trace_calls(probe_trace_func, modules=modules_in_summary)
    return y


@pytest.fixture()
def ref(
    ref_trace_func: Mock,
    modules_in_summary: Set[str] | None,
    run_ref,
) -> TraceSummary:
    _ = run_ref
    y = summarize_trace_calls(ref_trace_func, modules=modules_in_summary)
    return y


@pytest.fixture()
def modules_in_summary() -> Set[str] | None:
    return None


@pytest.fixture()
def run_target(
    func: Callable[[], Any],
    wrap_target_trace_func: Mock,
    thread: bool,
) -> None:
    call_with_trace(func=func, trace=wrap_target_trace_func, thread=thread)
    return


@pytest.fixture()
def run_ref(
    func: Callable[[], Any],
    ref_trace_func: Mock,
    thread: bool,
) -> None:
    call_with_trace(func=func, trace=ref_trace_func, thread=thread)
    return


@pytest.fixture()
def wrap_target_trace_func(target_trace_func: TraceFunc) -> Mock:
    wrap = Mock(wraps=target_trace_func)

    def side_effect(*a, **k):
        local_trace_func = target_trace_func(*a, **k)
        if local_trace_func is target_trace_func:
            return wrap
        return local_trace_func

    wrap.side_effect = side_effect
    return wrap


@pytest.fixture()
def probe_trace_func() -> Mock:
    y = Mock()
    y.return_value = y
    return y


@pytest.fixture()
def ref_trace_func() -> Mock:
    y = Mock()
    y.return_value = y
    return y
