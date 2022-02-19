import pytest
from unittest.mock import Mock

from typing import Set

from nextline.call import call_with_trace
from nextline.trace import TraceAddFirstModule
from nextline.types import TraceFunc

from .funcs import summarize_trace_calls, TraceSummaryType

from . import module_a, module_b


def test_one(
    obj_call_summary: TraceSummaryType,
    trace_call_summary: TraceSummaryType,
    modules_to_trace: Set[str],
):
    expected = {
        func.__name__,
        module_a.func_a.__name__,
        module_b.func_b.__name__,
    }
    assert expected <= obj_call_summary["func"]["call"]
    assert expected <= trace_call_summary["func"]["return"]

    assert "return" not in obj_call_summary["func"]

    assert {__name__} == modules_to_trace


@pytest.fixture()
def mock_trace():
    y = Mock()
    y.return_value = y
    yield y


@pytest.fixture()
def modules_to_trace():
    y = set()
    yield y


@pytest.fixture()
def obj(mock_trace: Mock, modules_to_trace: Set[str]):
    y = TraceAddFirstModule(
        trace=mock_trace,
        modules_to_trace=modules_to_trace,
    )
    y = Mock(wraps=y)
    yield y


@pytest.fixture()
def obj_call_summary(obj: TraceFunc):
    call_with_trace(func=func, trace=obj, thread=False)
    y = summarize_trace_calls(obj)
    yield y


@pytest.fixture()
def trace_call_summary(obj_call_summary, mock_trace: Mock):
    assert obj_call_summary is not None
    y = summarize_trace_calls(mock_trace)
    yield y


def func():
    module_a.func_a()
