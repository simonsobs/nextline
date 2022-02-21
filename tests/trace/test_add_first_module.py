import pytest
from unittest.mock import Mock

from typing import Set

from nextline.trace import TraceAddFirstModule

from .funcs import TraceSummary

from . import module_a


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    modules_to_trace: Set[str],
    modules_to_trace_init: Set[str],
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call.module == target.call.module
    assert not target.return_.module
    assert ref.call.module == probe.call.module
    assert ref.return_.module == probe.return_.module

    assert modules_to_trace_init is not modules_to_trace
    assert {__name__} | modules_to_trace_init == modules_to_trace


def f():
    module_a.func_a()


@pytest.fixture()
def func():
    yield f


@pytest.fixture(params=[set(), {"some_module"}])
def modules_to_trace_init(request):
    y = request.param
    yield y


@pytest.fixture()
def modules_to_trace(modules_to_trace_init):
    y = set(modules_to_trace_init)
    yield y


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, modules_to_trace: Set[str]):
    y = TraceAddFirstModule(
        trace=probe_trace_func,
        modules_to_trace=modules_to_trace,
    )
    yield y


@pytest.fixture()
def thread():
    yield False
