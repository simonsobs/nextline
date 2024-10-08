from types import FrameType
from typing import Any, Callable, Optional
from unittest.mock import Mock

import pytest

from nextline.spawned.types import TraceFunction

from . import module_a
from .funcs import TraceSummary


def Filter(
    trace: TraceFunction, filter: Callable[[FrameType, str, Any], bool]
) -> TraceFunction:
    '''Skip if the filter returns False.'''

    def _trace(frame: FrameType, event: str, arg: Any) -> Optional[TraceFunction]:
        if filter(frame, event, arg):
            return trace(frame, event, arg)
        return None

    return _trace


def FilterLambda(trace: TraceFunction) -> TraceFunction:
    '''An example filter'''

    def filter(frame: FrameType, event: str, arg: Any) -> bool:
        del event, arg
        func_name = frame.f_code.co_name
        return not func_name == '<lambda>'

    return Filter(trace=trace, filter=filter)


def test_one(target: TraceSummary, probe: TraceSummary, ref: TraceSummary) -> None:
    assert ref.call.func
    assert ref.return_.func
    assert ref.call.func == target.call.func
    assert not target.return_.func
    assert set(ref.call.func) - {"<lambda>"} == set(probe.call.func)
    assert set(ref.return_.func) - {"<lambda>"} == set(probe.return_.func)


def f() -> None:
    module_a.func_a()


def g() -> None:
    (lambda: module_a.func_a())()


@pytest.fixture(params=[f, g, lambda: module_a.func_a()])
def func(request: pytest.FixtureRequest) -> Callable[[], Any]:
    return request.param


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock) -> TraceFunction:
    y = FilterLambda(trace=probe_trace_func)
    return y
