from __future__ import annotations

from asyncio import Task
from threading import Thread
from typing import MutableMapping, Set

from apluggy import PluginManager

from nextline.process.callback.spec import hookimpl
from nextline.process.io import CurrentTaskOrThreadIfInCollection, peek_stdout_by_key
from nextline.types import TraceNo
from nextline.utils import current_task_or_thread


class PeekStdout:
    def __init__(
        self,
        trace_no_map: MutableMapping[Task | Thread, TraceNo],
        hook: PluginManager,
    ) -> None:
        self._tasks_and_threads: Set[Task | Thread] = set()
        self._trace_no_map = trace_no_map
        self._hook = hook

    def _stdout(self, task_or_thread: Task | Thread, line: str):
        trace_no = self._trace_no_map[task_or_thread]
        self._hook.hook.stdout(trace_no=trace_no, line=line)

    @hookimpl
    def task_or_thread_start(self) -> None:
        task_or_thread = current_task_or_thread()
        self._tasks_and_threads.add(task_or_thread)

    @hookimpl
    def start(self) -> None:
        to_peek = self._tasks_and_threads
        key_factory = CurrentTaskOrThreadIfInCollection(collection=to_peek)
        self._peek_stdout = peek_stdout_by_key(  # type: ignore
            key_factory=key_factory, callback=self._stdout
        )
        self._peek_stdout.__enter__()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._peek_stdout.__exit__(exc_type, exc_value, traceback)
