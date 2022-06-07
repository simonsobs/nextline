from __future__ import annotations

from asyncio import Task
from collections import defaultdict
from contextlib import contextmanager
from threading import Thread
from typing import Any, Callable, DefaultDict, MutableSequence, TypeVar


from .utils import ThreadTaskDoneCallback, current_task_or_thread
from .peek import peek_stdout


_T = TypeVar("_T")


@contextmanager
def peek_stdout_by_task_and_thread(
    to_peek: MutableSequence[Task | Thread],
    callback: Callable[[Task | Thread, str], Any],
):
    key_factory = KeyFactory(to_return=to_peek)
    read_lines = ReadLines(callback)
    assign_key = AssignKey(key_factory=key_factory, callback=read_lines)  # type: ignore
    with peek_stdout(assign_key) as t:
        with key_factory:
            yield t


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
