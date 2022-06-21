import asyncio
from threading import Thread
from itertools import permutations

import pytest
from unittest.mock import Mock

from typing import List, MutableSequence, Sequence, Tuple, Set, Any

from nextline.process.call import call_with_trace
from nextline.process.trace import TraceDispatchThreadOrTask


@pytest.fixture()
def created() -> List[Mock]:
    """List of mock objects created by the factory fixture"""
    return []


@pytest.fixture()
def factory(created: MutableSequence[Mock]) -> Mock:
    """Function that creates a Mock object that returns itself

    Created Mock objects are used as trace functions.

    The fixture "created" contains the created objects.
    """

    def side_effect():
        trace_func = Mock()
        trace_func.return_value = trace_func
        created.append(trace_func)
        return trace_func

    y = Mock(side_effect=side_effect)
    return y


def f_pass():
    pass


def f_call():
    return f_pass()


def f_thread():
    t = Thread(target=f_call)
    t.start()
    t.join()


async def a_sleep():
    await asyncio.sleep(0)
    await asyncio.sleep(0.001)


def a_run():
    asyncio.run(a_sleep())


async def a_task():
    t1 = asyncio.create_task(a_sleep())
    t2 = asyncio.create_task(a_sleep())
    await asyncio.gather(t1, t2)


def a_run_task():
    asyncio.run(a_task())


def f_thread_run_task():
    t = Thread(target=a_run_task)
    t.start()
    t.join()


params = [
    pytest.param(
        f_pass,
        [{(__name__, f_pass.__name__)}],
    ),
    pytest.param(
        f_call,
        [{(__name__, f_call.__name__), (__name__, f_pass.__name__)}],
    ),
    pytest.param(
        f_thread,
        [
            {(__name__, f_thread.__name__)},
            {(__name__, f_call.__name__), (__name__, f_pass.__name__)},
        ],
    ),
    pytest.param(
        a_run,
        [{(__name__, a_run.__name__)}, {(__name__, a_sleep.__name__)}],
    ),
    pytest.param(
        a_run_task,
        [
            {(__name__, a_run_task.__name__)},
            {(__name__, a_task.__name__)},
            {(__name__, a_sleep.__name__)},
            {(__name__, a_sleep.__name__)},
        ],
    ),
    pytest.param(
        f_thread_run_task,
        [
            {(__name__, f_thread_run_task.__name__)},
            {(__name__, a_run_task.__name__)},
            {(__name__, a_task.__name__)},
            {(__name__, a_sleep.__name__)},
            {(__name__, a_sleep.__name__)},
        ],
    ),
]


@pytest.mark.parametrize("func, expected", params)
def test_one(factory: Mock, created: MutableSequence[Mock], func, expected):
    obj = TraceDispatchThreadOrTask(factory=factory)
    call_with_trace(func, obj)
    print()
    # print(traced(created))
    actual = traced(created)
    # print(actual)
    # print(len(actual))
    assert is_unordered_list_of_subsets(expected, actual)


def traced(created: Sequence[Mock]) -> List[Set[Tuple[str, str]]]:
    """A list of sets, each with tuples of traced module and func names

    e.g., [{("module", "func"), ...}, ...]
    """
    args_list = [
        [call.args for call in mock.call_args_list] for mock in created
    ]
    return [
        {
            (frame.f_globals.get("__name__"), frame.f_code.co_name)
            for frame, event, _ in args
            if event == "return"
        }
        for args in args_list
    ]


def is_list_of_subsets(
    sets1: Sequence[Set[Any]], sets2: Sequence[Set[Any]]
) -> bool:
    if not len(sets1) <= len(sets2):
        return False
    intersections = [s1 & s2 for s1, s2 in zip(sets1, sets2)]
    return sets1 == intersections


def is_unordered_list_of_subsets(
    sets1: Sequence[Set[Any]], sets2: Sequence[Set[Any]]
) -> bool:
    for p in permutations(sets2):
        if is_list_of_subsets(sets1, p):
            return True
    return False


params = [
    pytest.param([], [], True),
    pytest.param([], [set()], True),
    pytest.param([set()], [], False),
    pytest.param([set()], [set()], True),
    pytest.param([{1}], [{1}], True),
    pytest.param([{1}], [{1}, {2}], True),
    pytest.param([{1}], [{1, 2}], True),
    pytest.param([{1}], [{2}], False),
    pytest.param([{1}, {2}], [{1, 10}, {2, 20}], True),
    pytest.param([{1}, {2}], [{2, 20}, {1, 10}], True),
    pytest.param([{1}, {2}], [{1, 10}, {3, 30}], False),
    pytest.param([{1}, {2}], [{3, 30}, {1, 10}], False),
    pytest.param([{1}, {1}, {2}], [{1, 10}, {2, 20}], False),
    pytest.param([{1}, {1}, {2}], [{1, 10}, {1, 30}, {2, 20}], True),
]


@pytest.mark.parametrize("sets1, sets2, expected", params)
def test_is_unordered_list_of_subset(
    sets1: Sequence[Set[Any]], sets2: Sequence[Set[Any]], expected: bool
):
    assert is_unordered_list_of_subsets(sets1, sets2) is expected
