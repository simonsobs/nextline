from functools import partial
from typing import Set
from unittest.mock import Mock

import pytest

from nextline.process.trace.wrap import TraceAddFirstModule

from . import module_a
from .funcs import TraceSummary


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    modules_to_trace: Set[str],
    modules_to_trace_init: Set[str],
    module_name: str,
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call == target.call
    assert not target.return_.module
    assert ref == probe

    assert modules_to_trace_init is not modules_to_trace
    assert {module_name} | modules_to_trace_init == modules_to_trace


def f1():
    module_a.func_a()


f2 = partial(f1)

statement = """
module_a.func_a()
"""

code = compile(statement, "<string>", "exec")
globals_ = {"module_a": module_a}  # without __name__
f3 = partial(exec, code, globals_)


@pytest.fixture(
    params=[
        (f1, __name__),
        (f2, __name__),
        (f3, module_a.__name__),
    ]
)
def func_and_module_name(request):
    return request.param


@pytest.fixture()
def func(func_and_module_name):
    return func_and_module_name[0]


@pytest.fixture()
def module_name(func_and_module_name):
    return func_and_module_name[1]


@pytest.fixture(params=[set(), {"some_module"}])
def modules_to_trace_init(request):
    y = request.param
    return y


@pytest.fixture()
def modules_to_trace(modules_to_trace_init):
    y = set(modules_to_trace_init)
    return y


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, modules_to_trace: Set[str]):
    y = TraceAddFirstModule(
        trace=probe_trace_func,
        modules_to_trace=modules_to_trace,
    )
    return y
