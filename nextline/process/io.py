from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict, TypeVar

from nextline.utils import peek_stdout

_T = TypeVar('_T')


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
