from __future__ import annotations

import sys
import threading
import timeit

from nextline.process.trace.main import MODULES_TO_SKIP
from nextline.process.trace.wrap import FilterByModuleName
from nextline.utils import profile_func


def test_one():
    trace = FilterByModuleName(
        trace=lambda *_: None,
        patterns=MODULES_TO_SKIP,
    )
    frame = sys._current_frames()[threading.current_thread().ident]
    # t = timeit.timeit(lambda: trace(frame, "line", None), number=20_000)
    t = timeit.timeit(lambda: trace(frame, "line", None), number=200_000)
    # t = timeit.timeit(lambda: trace(frame, "line", None), number=2_000_000)
    # print()
    # print(t)

    def func():
        for _ in range(20_000):
            trace(frame, "line", None)

    profile, _ = profile_func(func)
    # print(profile)
