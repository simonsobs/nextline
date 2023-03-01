from __future__ import annotations

import sys
import threading
import timeit
from typing import TYPE_CHECKING

import pytest

from nextline.process.callback import MODULES_TO_SKIP
from nextline.process.trace.wrap import FilterByModuleName
from nextline.utils import profile_func

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


def test_timeit(trace_func: TraceFunc):

    n_calls = 200_000

    thread_id = threading.current_thread().ident
    assert thread_id

    frame = sys._current_frames()[thread_id]

    sec = timeit.timeit(lambda: trace_func(frame, "line", None), number=n_calls)

    # print(f'{sec:.3f} seconds for {n_calls:,} calls')

    assert sec < 1


def test_profile(trace_func: TraceFunc):
    '''Used to print the profile.'''

    n_calls = 20_000

    thread_id = threading.current_thread().ident
    assert thread_id

    frame = sys._current_frames()[thread_id]

    def func():
        for _ in range(n_calls):
            trace_func(frame, "line", None)

    profile, _ = profile_func(func)

    # print(profile)


@pytest.fixture()
def trace_func():
    return FilterByModuleName(trace=lambda *_: None, patterns=MODULES_TO_SKIP)
