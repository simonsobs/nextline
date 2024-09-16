import sys
import threading
import timeit

import pytest

from nextline.spawned.plugin.plugins import FilterByModuleName
from nextline.spawned.plugin.skip import MODULES_TO_SKIP
from nextline.utils import profile_func


def test_timeit(plugin: FilterByModuleName) -> None:
    n_calls = 200_000

    thread_id = threading.current_thread().ident
    assert thread_id

    frame = sys._current_frames()[thread_id]

    sec = timeit.timeit(lambda: plugin.filter((frame, "line", None)), number=n_calls)

    # print(f'{sec:.3f} seconds for {n_calls:,} calls')

    assert sec < 1


def test_profile(plugin: FilterByModuleName) -> None:
    '''Used to print the profile.'''

    n_calls = 20_000

    thread_id = threading.current_thread().ident
    assert thread_id

    frame = sys._current_frames()[thread_id]

    def func() -> None:
        for _ in range(n_calls):
            plugin.filter((frame, "line", None))

    profile, _ = profile_func(func)

    # print(profile)


@pytest.fixture()
def plugin() -> FilterByModuleName:
    p = FilterByModuleName()
    p.init(modules_to_skip=MODULES_TO_SKIP)
    return p
