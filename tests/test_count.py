from hypothesis import given
from hypothesis import strategies as st

from nextline.count import (
    PromptNoCounter,
    RunNoCounter,
    TaskNoCounter,
    ThreadNoCounter,
    TraceNoCounter,
)
from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceNo
from tests.test_utils.st import st_none_or

COUNT_COUNTER_PAIRS = [
    (RunNoCounter, RunNo),
    (TraceNoCounter, TraceNo),
    (ThreadNoCounter, ThreadNo),
    (TaskNoCounter, TaskNo),
    (PromptNoCounter, PromptNo),
]


@given(
    pair=st.sampled_from(COUNT_COUNTER_PAIRS),
    start=st_none_or(st.integers()),
    n=st.integers(min_value=1, max_value=10),
)
def test_counter(pair, start: int | None, n: int) -> None:
    counter, count = pair
    if start is not None:
        counter = counter(start)
    else:
        counter = counter()
        start = 1
    for i in range(n):
        assert count(start + i) == counter()
