import pytest
from unittest.mock import Mock

from typing import Set, Dict

from nextline.call import call_with_trace
from nextline.trace import TraceAddFirstModule
from nextline.types import TraceFunc

from .funcs import summarize_trace_calls

from . import module_a


def test_one(trace_summary: Dict, modules_to_trace: Set):
    assert {__name__} == modules_to_trace
    assert {__name__, module_a.__name__} <= trace_summary["module"]["return"]


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
    yield y


@pytest.fixture()
def trace_summary(obj: TraceFunc, mock_trace: Mock):
    call_with_trace(func=func, trace=obj, thread=False)
    y = summarize_trace_calls(mock_trace)
    yield y


def func():
    module_a.func()
