from __future__ import annotations

import threading
from asyncio import Task
from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from threading import Thread
from typing import TYPE_CHECKING, Callable, MutableMapping, Optional, Tuple

from apluggy import PluginManager

from nextline.process.callback.spec import hookimpl
from nextline.process.callback.types import TraceArgs
from nextline.process.exc import TraceNotCalled
from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, TraceNo
from nextline.utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)

if TYPE_CHECKING:
    from nextline.process.callback import Callback


class CallbackForTrace:
    def __init__(
        self,
        trace_no: TraceNo,
        hook: PluginManager,
        callback: Callback,
        command_queue_map: CommandQueueMap,
        trace_id_factory: ThreadTaskIdComposer,
        prompt_no_counter: Callable[[], PromptNo],
    ):
        self._trace_no = trace_no
        self._hook = hook
        self._callback = callback
        self._command_queue_map = command_queue_map
        self._trace_id_factory = trace_id_factory
        self._prompt_no_counter = prompt_no_counter

        self._command_queue: Queue[Tuple[str, PromptNo, TraceNo]] = Queue()
        self._trace_args: TraceArgs | None = None

        self._logger = getLogger(__name__)

    def trace_start(self):
        thread_task_id = self._trace_id_factory()
        thread_no = thread_task_id.thread_no
        task_no = thread_task_id.task_no

        self._command_queue_map[self._trace_no] = self._command_queue = Queue()

        self._hook.hook.trace_start(
            trace_no=self._trace_no, thread_no=thread_no, task_no=task_no
        )

    def trace_end(self):
        self._hook.hook.trace_end(trace_no=self._trace_no)
        del self._command_queue_map[self._trace_no]

    @contextmanager
    def trace_call(self, trace_args: TraceArgs):
        self._trace_args = trace_args
        with self._hook.with_.trace_call(
            trace_no=self._trace_no, trace_args=trace_args
        ):
            try:
                yield
            finally:
                self._trace_args = None

    @contextmanager
    def cmdloop(self):
        if self._trace_args is None:
            raise TraceNotCalled
        with self._hook.with_.cmdloop(
            trace_no=self._trace_no, trace_args=self._trace_args
        ):
            yield

    def prompt(self, text: str) -> str:
        prompt_no = self._prompt_no_counter()
        self._logger.debug(f'PromptNo: {prompt_no}')
        with (
            p := self._hook.with_.prompt(
                trace_no=self._trace_no,
                prompt_no=prompt_no,
                trace_args=self._trace_args,
                out=text,
            )
        ):
            while True:
                command, prompt_no_, trace_no_ = self._command_queue.get()
                try:
                    assert trace_no_ == self._trace_no
                except AssertionError:
                    msg = f'TraceNo mismatch: {trace_no_} != {self._trace_no}'
                    self._logger.exception(msg)
                    raise
                if prompt_no_ == prompt_no:
                    break
                self._logger.warning(f'PromptNo mismatch: {prompt_no_} != {prompt_no}')
            p.gen.send(command)
        return command


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
