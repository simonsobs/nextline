from __future__ import annotations

from apluggy import PluginManager

from nextline.process.callback.spec import hookimpl
from nextline.process.io import peek_stdout_by_key
from nextline.types import TraceNo


class PeekStdout:
    def __init__(self, hook: PluginManager) -> None:
        self._hook = hook

    def _stdout(self, trace_no: TraceNo, line: str):
        self._hook.hook.stdout(trace_no=trace_no, line=line)

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:
        assert trace_no == self._key_factory()

    def _key_factory(self) -> TraceNo | None:
        return self._hook.hook.current_trace_no()

    @hookimpl
    def start(self) -> None:
        self._peek = peek_stdout_by_key(
            key_factory=self._key_factory, callback=self._stdout
        )
        self._peek.__enter__()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._peek.__exit__(exc_type, exc_value, traceback)
