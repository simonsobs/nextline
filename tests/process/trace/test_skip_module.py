import pytest
from unittest.mock import Mock

from typing import Set

from nextline.process.trace import TraceSkipModule

from .funcs import TraceSummary

from . import module_a


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    modules_to_skip: Set[str],
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call.module == target.call.module
    assert not target.return_.module
    assert set(ref.call.module) - modules_to_skip == set(probe.call.module)
    assert set(ref.call.module) - modules_to_skip == set(probe.return_.module)


def f():
    module_a.func_a()


@pytest.fixture()
def func():
    yield f


@pytest.fixture(params=[set(), {module_a.__name__}])
def modules_to_skip(request):
    y = request.param
    yield y


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, modules_to_skip: Set[str]):
    y = TraceSkipModule(
        trace=probe_trace_func,
        skip=modules_to_skip,
    )
    yield y


@pytest.fixture()
def thread():
    yield False
