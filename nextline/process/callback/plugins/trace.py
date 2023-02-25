from __future__ import annotations

import threading
from asyncio import Task
from threading import Thread
from typing import TYPE_CHECKING, MutableMapping, Optional

from nextline.process.callback.spec import hookimpl
from nextline.types import TraceNo
from nextline.utils import ThreadTaskDoneCallback, current_task_or_thread

if TYPE_CHECKING:
    from nextline.process.callback import Callback


class TaskOrThreadToTraceMapper:
    def __init__(
        self, callback: 'Callback', trace_no_map: MutableMapping[Task | Thread, TraceNo]
    ) -> None:
        self._callback = callback
        self._trace_no_map = trace_no_map
        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self._callback.task_or_thread_end
        )
        self._entering_thread: Optional[Thread] = None

    @hookimpl
    def task_or_thread_start(self, trace_no: TraceNo) -> None:
        task_or_thread = current_task_or_thread()
        self._trace_no_map[task_or_thread] = trace_no

        if task_or_thread is not self._entering_thread:
            self._thread_task_done_callback.register(task_or_thread)

        self._callback.trace_start(trace_no)

    @hookimpl
    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self._callback.trace_end(trace_no)

    @hookimpl
    def start(self) -> None:
        self._entering_thread = threading.current_thread()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._thread_task_done_callback.close()
        if self._entering_thread:
            if trace_no := self._trace_no_map.get(self._entering_thread):
                self._callback.trace_end(trace_no)
