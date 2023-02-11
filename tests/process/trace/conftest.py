from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Set
from unittest.mock import Mock

import pytest

from nextline.process.call import sys_trace

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

from .funcs import TraceSummary, summarize_trace_calls


@pytest.fixture()
def target(
    wrap_target_trace_func: Mock,
    modules_in_summary: Set[str] | None,
    run_target,
) -> TraceSummary:
    '''Summary of the calls to the target trace function.

    The target trace function is the trace function under test. It is wrapped by
    a mock object and given to sys.settrace() to collect trace calls.
    '''
    _ = run_target
    y = summarize_trace_calls(wrap_target_trace_func, modules=modules_in_summary)
    return y


@pytest.fixture()
def probe(
    probe_trace_func: Mock,
    modules_in_summary: Set[str] | None,
    run_target,
) -> TraceSummary:
    '''Summary of the calls to the probe trace function.

    The probe trace function is a mock object that can be called by the target
    trace function during the trace calls.
    '''
    _ = run_target
    y = summarize_trace_calls(probe_trace_func, modules=modules_in_summary)
    return y


@pytest.fixture()
def ref(
    ref_trace_func: Mock,
    modules_in_summary: Set[str] | None,
    run_ref,
) -> TraceSummary:
    '''Summary of the calls to the reference trace function.

    The reference trace function is a mock object that is given to sys.settrace()
    to collect trace calls without the target trace function.
    '''
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
    '''Call the func and collect the calls to the target and probe trace functions.'''
    with sys_trace(trace_func=wrap_target_trace_func, thread=thread):
        func()
    return


@pytest.fixture()
def run_ref(
    func: Callable[[], Any],
    ref_trace_func: Mock,
    thread: bool,
) -> None:
    '''Call the func and collect the calls to the reference trace function.'''
    with sys_trace(trace_func=ref_trace_func, thread=thread):
        func()
    return


@pytest.fixture()
def wrap_target_trace_func(target_trace_func: TraceFunc) -> Mock:
    '''A mock object wrapping the trace function under test to collect trace calls.'''
    wrap = Mock(wraps=target_trace_func)

    def side_effect(*a, **k):
        # Wrap again if the target returns itself.
        local_trace_func = target_trace_func(*a, **k)
        if local_trace_func is target_trace_func:
            return wrap
        return local_trace_func

    wrap.side_effect = side_effect
    return wrap


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock):
    '''The trace function under test. This fixture is to be overridden by the test.'''
    del probe_trace_func
    raise RuntimeError('This fixture must be overridden by the test')


@pytest.fixture()
def probe_trace_func() -> Mock:
    '''A mock object to be called by the target trace function.

    The calls to this fixture are compared to the calls to the reference trace
    function and the target trace function.
    '''
    y = Mock()
    y.return_value = y
    return y


@pytest.fixture()
def ref_trace_func() -> Mock:
    '''A mock object to be given to sys.settrace() to collect reference trace calls.'''
    y = Mock()
    y.return_value = y
    return y
