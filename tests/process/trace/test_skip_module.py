from typing import Set
from unittest.mock import Mock

import pytest

from nextline.process.trace.wrap import FilterByModuleName

from . import module_a
from .funcs import TraceSummary


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
    return f


@pytest.fixture(params=[set(), {module_a.__name__}])
def modules_to_skip(request):
    y = request.param
    return y


@pytest.fixture()
def target_trace_func(probe_trace_func: Mock, modules_to_skip: Set[str]):
    y = FilterByModuleName(
        trace=probe_trace_func,
        patterns=modules_to_skip,
    )
    return y
