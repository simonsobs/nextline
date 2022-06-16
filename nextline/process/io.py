from __future__ import annotations

from asyncio import Task
from collections import defaultdict
from contextlib import contextmanager
from threading import Thread
from typing import Any, Callable, Collection, DefaultDict, TypeVar


from ..utils import current_task_or_thread, peek_stdout


_T = TypeVar("_T")


@contextmanager
def peek_stdout_by_task_and_thread(
    to_peek: Collection[Task | Thread],
    callback: Callable[[Task | Thread, str], Any],
):
    key_factory = KeyFactory(to_register=to_peek)
    read_lines = ReadLines(callback)
    assign_key = AssignKey(key_factory=key_factory, callback=read_lines)  # type: ignore
    with peek_stdout(assign_key) as t:
        yield t


def KeyFactory(
    to_register: Collection[Task | Thread],
) -> Callable[[], Task | Thread | None]:
    def key_factory() -> Task | Thread | None:
        if (key := current_task_or_thread()) in to_register:
            return key
        return None

    return key_factory


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
