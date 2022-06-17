from __future__ import annotations

import cProfile
import pstats
from io import StringIO

from typing import Callable, TypeVar, Tuple

_T = TypeVar("_T")


def profile_func(func: Callable[[], _T]) -> Tuple[str, _T]:
    with cProfile.Profile() as pr:
        ret = func()
    sortby = "cumulative"
    s = StringIO()
    pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby).print_stats()
    return s.getvalue(), ret
