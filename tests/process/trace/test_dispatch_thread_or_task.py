from __future__ import annotations

import asyncio
from asyncio import Task
from threading import Thread

import pytest
from unittest.mock import Mock

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Mapping,
    MutableMapping,
    Set,
)

from nextline.process.trace import TraceDispatchThreadOrTask
from nextline.utils import current_task_or_thread
from nextline.utils import ExcThread

if TYPE_CHECKING:
    from sys import _TraceFunc as TraceFunc

from .funcs import TraceSummary, summarize_trace_calls

from . import module_a, module_b


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    factory: Mock,
    probes: Mapping[Task | Thread, TraceSummary],
    probe_trace_funcs: Mapping[Task | Thread, Mock],
    task_or_threads: Mapping[Task | Thread, Set[Task | Thread]],
    modules_in_summary: Set[str],
):
    assert modules_in_summary is not None
    assert ref.call.module
    assert ref.return_.module
    assert ref.call.func == target.call.func
    assert not target.return_.func

    assert factory.call_count == len(task_or_threads)
    assert probe_trace_funcs.keys() == task_or_threads.keys()
    assert probes.keys() == task_or_threads.keys()

    for created_in, called_in in task_or_threads.items():
        assert {created_in} == called_in

    assert ref.call.func == probe.call.func
    assert ref.return_.func == probe.return_.func


@pytest.fixture()
def modules_in_summary():
    return {__name__, module_a.__name__, module_b.__name__}


def f1():
    module_a.func_a()


def f2():
    t = ExcThread(target=module_a.func_a)
    t.start()
    t.join()


def f3():
    async def a():
        module_a.func_a()

    asyncio.run(a())


def f4():
    t = ExcThread(target=f3)
    t.start()
    t.join()


@pytest.fixture(params=[f1, f2, f3, f4])
def func(request) -> Callable[[], Any]:
    return request.param


@pytest.fixture()
def target_trace_func(factory: Mock) -> TraceFunc:
    return TraceDispatchThreadOrTask(factory=factory)


@pytest.fixture(params=[True, False])
def thread(request) -> bool:
    return request.param


@pytest.fixture()
def probes(
    probe_trace_funcs: MutableMapping[Task | Thread, Mock],
    modules_in_summary: Set[str] | None,
):
    y = {
        k: summarize_trace_calls(v, modules=modules_in_summary)
        for k, v in probe_trace_funcs.items()
    }
    return y


@pytest.fixture()
def factory(
    probe_trace_funcs: MutableMapping[Task | Thread, Mock],
    task_or_threads: MutableMapping[Task | Thread, Set[Task | Thread]],
    probe_trace_func: Mock,
) -> Mock:
    def factory_():
        called_in = set()

        wrap_trace = Mock(wraps=probe_trace_func)

        def trace(*a, **k):
            called_in.add(current_task_or_thread())
            local_trace = probe_trace_func(*a, **k)
            if local_trace is probe_trace_func:
                return wrap_trace
            return local_trace

        wrap_trace.side_effect = trace

        created_in = current_task_or_thread()
        task_or_threads[created_in] = called_in
        probe_trace_funcs[created_in] = wrap_trace
        return wrap_trace

    return Mock(wraps=factory_)


@pytest.fixture()
def probe_trace_funcs() -> Dict[Task | Thread, Mock]:
    return {}


@pytest.fixture()
def task_or_threads():
    return {}
