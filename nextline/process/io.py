from __future__ import annotations

from asyncio import Task
from collections import defaultdict
from threading import Thread
from typing import Any, Callable, Collection, DefaultDict, TypeVar

from typing_extensions import TypeAlias

from nextline.utils import current_task_or_thread, peek_stdout

_T = TypeVar('_T')
_Key: TypeAlias = 'Task | Thread'


def CurrentTaskOrThreadIfInCollection(
    collection: Collection[_Key],
) -> Callable[[], _Key | None]:
    def fn() -> _Key | None:
        if (key := current_task_or_thread()) in collection:
            return key
        return None

    return fn


def peek_stdout_by_key(
    key_factory: Callable[[], _T | None],
    callback: Callable[[_T, str], Any],
):
    callback_ = ReadLinesByKey(callback)
    assign_key = AssignKey(key_factory=key_factory, callback=callback_)
    return peek_stdout(assign_key)


def ReadLinesByKey(callback: Callable[[_T, str], Any]) -> Callable[[_T, str], Any]:
    buffer: DefaultDict[_T, str] = defaultdict(str)

    def read_lines_by_key(key: _T, s: str) -> None:
        buffer[key] += s
        if s.endswith('\n'):
            line = buffer.pop(key)
            callback(key, line)

    return read_lines_by_key


def AssignKey(
    key_factory: Callable[[], _T | None], callback: Callable[[_T, str], Any]
) -> Callable[[str], None]:
    def assign_key(s: str) -> None:
        if key := key_factory():
            callback(key, s)

    return assign_key
