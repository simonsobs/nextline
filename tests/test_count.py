from collections.abc import Callable
from typing import Protocol, TypeAlias

from hypothesis import given
from hypothesis import strategies as st

from nextline.count import (
    PromptNoCounter,
    RunNoCounter,
    TaskNoCounter,
    ThreadNoCounter,
    TraceCallNoCounter,
    TraceNoCounter,
)
from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceCallNo, TraceNo
from tests.test_utils.st import st_none_or

Counter: TypeAlias = Callable[[], int]


class CounterFactory(Protocol):
    def __call__(self, start: int = 1) -> Counter:
        ...


CounterCountPair: TypeAlias = tuple[CounterFactory, type[int]]

COUNTER_COUNT_PAIRS: list[CounterCountPair] = [
    (RunNoCounter, RunNo),
    (TraceNoCounter, TraceNo),
    (ThreadNoCounter, ThreadNo),
    (TaskNoCounter, TaskNo),
    (TraceCallNoCounter, TraceCallNo),
    (PromptNoCounter, PromptNo),
]


@given(
    pair=st.sampled_from(COUNTER_COUNT_PAIRS),
    start=st_none_or(st.integers()),
    n=st.integers(min_value=1, max_value=10),
)
def test_counter(pair: CounterCountPair, start: int | None, n: int) -> None:
    counter_factory, count = pair
    if start is not None:
        counter = counter_factory(start)
    else:
        counter = counter_factory()
        start = 1
    for i in range(n):
        assert count(start + i) == counter()
