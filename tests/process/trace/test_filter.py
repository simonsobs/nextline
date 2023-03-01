from __future__ import annotations

from types import FrameType
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from nextline.process.trace.wrap import Filter

from . import module_a
from .funcs import TraceSummary

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


def FilterLambda(trace: TraceFunc) -> TraceFunc:
    '''An example filter'''
    def filter(frame: FrameType, event, arg) -> bool:
        del event, arg
        func_name = frame.f_code.co_name
        return not func_name == '<lambda>'

    return Filter(trace=trace, filter=filter)


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
    return request.param


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock):
    y = FilterLambda(trace=probe_trace_func)
    return y
