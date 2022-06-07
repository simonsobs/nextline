from __future__ import annotations
from asyncio import Task
from collections import defaultdict
from contextlib import contextmanager
from itertools import groupby
from operator import itemgetter
import random
import string
import time
from threading import Thread
from typing import (
    Any,
    Callable,
    DefaultDict,
    Iterator,
    MutableSequence,
    Optional,
    TextIO,
    TypeVar,
)


from nextline.utils import ThreadTaskDoneCallback, current_task_or_thread
from nextline.peek import peek_stdout


from unittest.mock import Mock

_T = TypeVar("_T")


class KeyFactory:
    def __init__(self, to_return: MutableSequence[Task | Thread]):
        self._to_return = to_return
        self._callback = ThreadTaskDoneCallback()

    def __call__(self) -> Task | Thread | None:
        if current_task_or_thread() not in self._to_return:
            return None
        return self._callback.register()

    def close(self) -> None:
        return self._callback.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        self.close()


def ReadLines(callback: Callable[[_T, str], Any]) -> Callable[[_T, str], Any]:
    buffer: DefaultDict[_T, str] = defaultdict(str)

    def read_lines(key: _T, s: str) -> None:
        buffer[key] += s
        if s.endswith("\n"):
            line = buffer.pop(key)
            callback(key, line)

    return read_lines


def AssignKey(
    key_factory: Callable[[], _T | None], callback: Callable[[_T, str], Any]
) -> Callable[[str], None]:
    def assign_key(s: str) -> None:
        if key := key_factory():
            callback(key, s)

    return assign_key


@contextmanager
def peek_stdout_by_task_and_thread(
    to_peek: MutableSequence[Task | Thread],
    callback: Callable[[Task | Thread, str], Any],
):
    key_factory = KeyFactory(to_return=to_peek)
    read_lines = ReadLines(callback)
    w = AssignKey(key_factory=key_factory, callback=read_lines)  # type: ignore
    with peek_stdout(w) as t:
        with key_factory:
            yield t


def print_lines(lines: Iterator[str], file: Optional[TextIO] = None):
    for line in lines:
        time.sleep(0.0001)
        print(line, file=file)


def test_one(capsys):
    config = (
        (tuple(random_strings()), True),
        (tuple(random_strings()), True),
        (tuple(random_strings()), False),
    )
    thread_added = tuple(
        (Thread(target=print_lines, args=(c[0],)),) + c for c in config
    )
    threads = tuple(c[0] for c in thread_added)
    to_return = [c[0] for c in thread_added if c[2]]
    callback = Mock()
    with peek_stdout_by_task_and_thread(to_peek=to_return, callback=callback):
        for t in threads:
            t.start()
    for t in threads:
        t.join()
    results = {
        k: "".join(v[1] for v in v)
        for k, v in groupby(
            sorted(
                (c.args for c in callback.call_args_list),
                key=lambda args: args[0].name,
            ),
            itemgetter(0),
        )
    }
    expected = {c[0]: "\n".join(c[1]) + "\n" for c in thread_added if c[2]}
    assert results == expected


def test_random_strings():
    lines = random_strings()
    assert all(isinstance(line, str) for line in lines)


def random_strings():
    n_lines_range = (100, 200)
    # n_lines_range = (3, 10)
    n_letters_per_line_range = (0, 300)
    # n_letters_per_line_range = (0, 5)
    # letters = string.printable
    letters = string.ascii_letters
    r = (
        "".join(
            random.choice(letters)
            for _ in range(random.randint(*n_letters_per_line_range))
        )
        for _ in range(random.randint(*n_lines_range))
    )
    return r
