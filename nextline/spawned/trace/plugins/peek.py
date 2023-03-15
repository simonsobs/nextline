from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict, TypeVar

from apluggy import PluginManager

from nextline.spawned.trace.spec import hookimpl
from nextline.types import TraceNo
from nextline.utils import peek_stdout


class PeekStdout:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def on_start_trace(self, trace_no: TraceNo) -> None:
        assert trace_no == self._key_factory()

    @hookimpl
    def start(self) -> None:
        self._peek = peek_stdout_by_key(
            key_factory=self._key_factory, callback=self._callback
        )
        self._peek.__enter__()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._peek.__exit__(exc_type, exc_value, traceback)

    def _key_factory(self) -> TraceNo | None:
        return self._hook.hook.current_trace_no()

    def _callback(self, trace_no: TraceNo, line: str):
        self._hook.hook.on_write_stdout(trace_no=trace_no, line=line)


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