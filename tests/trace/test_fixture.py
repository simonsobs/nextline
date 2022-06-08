from __future__ import annotations

import pytest
from unittest.mock import Mock

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from sys import _TraceFunc as TraceFunc


def test_wrap_target_trace_func(
    target_trace_func: Union[Mock, TraceFunc],
    wrap_target_trace_func: Union[Mock, TraceFunc],
):
    if target_trace_func is target_trace_func():
        assert wrap_target_trace_func is wrap_target_trace_func()
    else:
        assert target_trace_func() is wrap_target_trace_func()


@pytest.fixture(params=["self", "another", "none"])
def target_trace_func(request, another_trace_func):
    y = Mock()
    map = {"self": y, "another": another_trace_func, "none": None}
    y.return_value = map[request.param]
    yield y


@pytest.fixture()
def another_trace_func():
    y = Mock()
    y.return_value = y
    yield y
