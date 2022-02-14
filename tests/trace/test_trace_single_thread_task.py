import asyncio
from threading import Thread

from dataclasses import dataclass

import pytest
from unittest.mock import Mock

from nextline.call import call_with_trace
from nextline.trace import TraceSingleThreadTask

from typing import Optional, Callable, Coroutine, List, Set, Any

from textwrap import indent
from pprint import pformat

pytestmark = pytest.mark.skip(reason="under development")


@dataclass
class call:
    module: str
    func: str
    event: str
    arg: Any


@dataclass
class trace:
    funcs: Set[str]
    calls: List[call]

    def __str__(self) -> str:
        prefix = " " * 4
        return "\n".join(
            (
                "calls:",
                indent("\n".join([str(c) for c in self.calls]), prefix),
            )
        )


@dataclass
class Result:
    ntraces: int
    funcs_each: Set[Set[str]]
    funcs_union: Set[str]
    traces: List[trace]

    def __str__(self) -> str:
        prefix = " " * 4
        return "\n".join(
            (
                "traces:",
                indent("\n".join([str(t) for t in self.traces]), prefix),
                "funcs_each:",
                indent(
                    "\n".join([pformat(set(s)) for s in self.funcs_each]),
                    prefix,
                ),
                f"ntraces: {self.ntraces}",
            )
        )


def unpack_(trace_func: Mock) -> List[call]:
    calls = [
        call(
            module=c.args[0].f_globals.get("__name__"),
            func=c.args[0].f_code.co_name,
            event=c.args[1],
            arg=c.args[2],
        )
        for c in trace_func.call_args_list
    ]
    funcs = {c.func for c in calls}
    return trace(funcs=funcs, calls=calls)


def unpack(trace_funcs: List[Mock]) -> Result:
    traces = [unpack_(t) for t in trace_funcs]
    funcs_each = {frozenset(t.funcs) for t in traces}
    funcs_union = {f for e in funcs_each for f in e}
    return Result(
        ntraces=len(traces),
        funcs_each=funcs_each,
        funcs_union=funcs_union,
        traces=traces,
    )


@pytest.fixture()
def trace_funcs():
    """Mock objects created by the factory fixture"""
    yield []


@pytest.fixture()
def trace_func_factory(trace_funcs: List[Mock]):
    """Function that each time creates a new instance of Mock

    The fixture trace_funcs will contain the created instances.
    """

    def side_effect():
        trace_func = Mock()
        trace_func.return_value = trace_func
        trace_funcs.append(trace_func)
        return trace_func

    factory = Mock(side_effect=side_effect)
    yield factory


def test_fixture(trace_func_factory: Mock, trace_funcs: List[Mock]):
    assert not trace_funcs
    t1 = trace_func_factory()
    assert [t1] == trace_funcs
    t2 = trace_func_factory()
    assert [t1, t2] == trace_funcs
    assert t1 is not t2


@pytest.fixture()
def obj(trace_func_factory: Mock, trace_funcs: List[Mock]):
    y = TraceSingleThreadTask(wrapped_factory=trace_func_factory)
    yield y


def f_empty():
    return


def f_func():
    f_empty()
    return


def f_thread():
    t = Thread(target=f_empty)
    t.start()
    t.join()
    return


async def a_empty():
    return


async def a_sleep():
    await asyncio.sleep(0)


async def a_create_task():
    await asyncio.create_task(asyncio.sleep(0))


def f_async_run_a_empty():
    asyncio.run(a_empty())


def f_thread_async_run_a_empty():
    t = Thread(target=asyncio.run, args=(a_empty(),))
    t.start()
    t.join()
    return


# TODO: exception, generator, async generator, lambda, code


@dataclass
class Expected:
    ntraces: Optional[int] = None
    ntraces_min: Optional[int] = None
    funcs_union: Optional[Set[str]] = None
    funcs_union_include: Optional[Set[str]] = None


params = [
    pytest.param(
        f_empty,
        Expected(
            ntraces=1,
            funcs_union={"f_empty"},
        ),
    ),
    pytest.param(
        f_func,
        Expected(
            ntraces=1,
            funcs_union={"f_func", "f_empty"},
        ),
    ),
    pytest.param(
        f_thread,
        Expected(
            ntraces=2,
            funcs_union_include={"f_thread", "f_empty"},
        ),
    ),
    pytest.param(
        f_async_run_a_empty,
        Expected(
            ntraces_min=3,
            funcs_union_include={"f_async_run_a_empty", "a_empty"},
        ),
    ),
    pytest.param(
        f_thread_async_run_a_empty,
        Expected(
            ntraces_min=3,
            funcs_union_include={"f_thread_async_run_a_empty", "a_empty"},
        ),
        marks=pytest.mark.skip(reason="temp"),
    ),
]


@pytest.mark.parametrize("func, expected", params)
def test_one(
    obj: TraceSingleThreadTask,
    trace_func_factory: Mock,
    trace_funcs: List[Mock],
    func: Callable,
    expected: Expected,
):
    call_with_trace(func, obj)
    result = unpack(trace_funcs)
    assert 0 == len(obj)
    # print()
    # print(result)
    assert_result(result, expected)


params = [
    pytest.param(
        a_empty,
        Expected(
            ntraces_min=2,
            funcs_union_include={"a_empty"},
        ),
    ),
    pytest.param(
        a_sleep,
        Expected(
            ntraces_min=2,
            funcs_union_include={"a_sleep"},
        ),
    ),
    pytest.param(
        a_create_task,
        Expected(
            ntraces_min=2,
            funcs_union_include={"a_create_task"},
        ),
    ),
]


@pytest.mark.parametrize("afunc, expected", params)
def test_async(
    obj: TraceSingleThreadTask,
    trace_func_factory: Mock,
    trace_funcs: List[Mock],
    afunc: Callable[[Any, Any], Coroutine[Any, Any, Any]],
    expected: Expected,
):
    def func():
        asyncio.run(afunc())

    call_with_trace(func, obj)
    result = unpack(trace_funcs)
    assert 0 == len(obj)
    # print()
    # print(result)
    assert_result(result, expected)


def assert_result(result: Result, expected: Expected) -> None:

    if expected.ntraces is not None:
        assert expected.ntraces == result.ntraces
    if expected.ntraces_min is not None:
        assert expected.ntraces_min <= result.ntraces
    if expected.funcs_union is not None:
        assert expected.funcs_union == result.funcs_union
    if expected.funcs_union_include is not None:
        assert expected.funcs_union_include <= result.funcs_union
