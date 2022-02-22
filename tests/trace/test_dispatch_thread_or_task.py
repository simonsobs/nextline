import asyncio
from asyncio import Task
from threading import Thread

import pytest
from unittest.mock import Mock

from typing import Union, Callable, Dict, Set

from nextline.trace import TraceDispatchThreadOrTask
from nextline.utils import current_task_or_thread
from nextline.types import TraceFunc
from nextline.utils import ExcThread

from .funcs import TraceSummary, summarize_trace_calls

from . import module_a, module_b


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    factory: Union[Mock, Callable[[], Union[Mock, TraceFunc]]],
    probes: Dict[Union[Task, Thread], TraceSummary],
    probe_trace_funcs: Dict[Union[Task, Thread], Union[Mock, TraceFunc]],
    task_or_threads: Dict[Union[Task, Thread], Set[Union[Task, Thread]]],
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
    yield {__name__, module_a.__name__, module_b.__name__}


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
def func(request):
    yield request.param


@pytest.fixture()
def target_trace_func(factory: Mock):
    y = TraceDispatchThreadOrTask(factory=factory)
    yield y


@pytest.fixture(params=[True, False])
def thread(request):
    y = request.param
    yield y


@pytest.fixture()
def probes(
    probe_trace_funcs: Dict[Union[Task, Thread], Union[Mock, TraceFunc]],
    modules_in_summary: Union[Set[str], None],
):
    y = {
        k: summarize_trace_calls(v, modules=modules_in_summary)
        for k, v in probe_trace_funcs.items()
    }
    yield y


@pytest.fixture()
def factory(probe_trace_funcs, task_or_threads, probe_trace_func):
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

    yield Mock(wraps=factory_)


@pytest.fixture()
def probe_trace_funcs():
    yield {}


@pytest.fixture()
def task_or_threads():
    yield {}
