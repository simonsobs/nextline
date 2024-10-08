from unittest.mock import Mock

import pytest

from nextline.spawned.types import TraceFunction


def test_wrap_target_trace_func(
    target_trace_func: Mock | TraceFunction,
    wrap_target_trace_func: Mock | TraceFunction,
) -> None:
    arg = (Mock(), "", None)
    if target_trace_func is target_trace_func(*arg):
        assert wrap_target_trace_func is wrap_target_trace_func(*arg)
    else:
        assert target_trace_func(*arg) is wrap_target_trace_func(*arg)


@pytest.fixture(params=["self", "another", "none"])
def target_trace_func(
    request: pytest.FixtureRequest, another_trace_func: TraceFunction
) -> TraceFunction:
    y = Mock()
    map = {"self": y, "another": another_trace_func, "none": None}
    y.return_value = map[request.param]
    return y


@pytest.fixture()
def another_trace_func() -> TraceFunction:
    y = Mock()
    y.return_value = y
    return y
