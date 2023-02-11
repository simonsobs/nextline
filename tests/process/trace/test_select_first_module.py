from typing import Set
from unittest.mock import Mock

import pytest

from nextline.process.trace import TraceSelectFirstModule

from . import module_a
from .funcs import TraceSummary


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    modules_to_trace: Set[str],
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call.module == target.call.module
    assert not target.return_.module
    expected = (
        max(
            [ref.call.module[ref.call.module.index(m) :] for m in modules_to_trace],
            key=len,
        )
        if modules_to_trace
        else []
    )
    assert expected == probe.call.module
    assert set(expected) == set(probe.return_.module)


def f():
    module_a.func_a()


@pytest.fixture()
def func():
    return f


@pytest.fixture(
    params=[
        set(),
        {__name__},
        {module_a.__name__},
        {__name__, module_a.__name__},
    ]
)
def modules_to_trace(request):
    y = request.param
    return y


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, modules_to_trace: Set[str]):
    y = TraceSelectFirstModule(
        trace=probe_trace_func,
        modules_to_trace=modules_to_trace,
    )
    return y
