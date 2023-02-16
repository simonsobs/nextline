from __future__ import annotations

import threading
from asyncio import Task
from contextlib import contextmanager
from threading import Thread
from typing import Optional, Set  # noqa F401
from weakref import WeakKeyDictionary

from nextline.types import PromptNo, RunNo, TraceNo
from nextline.utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)

from ..io import peek_stdout_by_task_and_thread
from .plugins import (
    AddModuleToTrace,
    PromptInfoRegistrar,
    RegistrarProxy,
    StdoutRegistrar,
    TraceArgs,
    TraceInfoRegistrar,
    TraceNoMap,
    TraceNumbersRegistrar,
)


class Callback:
    def __init__(
        self,
        run_no: RunNo,
        registrar: RegistrarProxy,
        modules_to_trace: Set[str],
    ):
        self._add_module_to_trace = AddModuleToTrace(modules_to_trace)
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._trace_id_factory = ThreadTaskIdComposer()
        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self.task_or_thread_end
        )
        self._tasks_and_threads: Set[Task | Thread] = set()
        self._entering_thread: Optional[Thread] = None
        self._trace_numbers_registrar = TraceNumbersRegistrar(registrar=registrar)
        self._trace_info_registrar = TraceInfoRegistrar(
            run_no=run_no, registrar=registrar
        )
        self._prompt_info_registrar = PromptInfoRegistrar(
            run_no=run_no, registrar=registrar
        )
        self._stdout_registrar = StdoutRegistrar(run_no=run_no, registrar=registrar)

    def task_or_thread_start(self, trace_no: TraceNo) -> None:
        task_or_thread = current_task_or_thread()
        self._trace_no_map[task_or_thread] = trace_no

        if task_or_thread is not self._entering_thread:
            self._thread_task_done_callback.register(task_or_thread)

        self._tasks_and_threads.add(task_or_thread)

        self.trace_start(trace_no)

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self.trace_end(trace_no)

    def trace_start(self, trace_no: TraceNo):
        self._trace_numbers_registrar.trace_start(trace_no=trace_no)

        thread_task_id = self._trace_id_factory()
        thread_no = thread_task_id.thread_no
        task_no = thread_task_id.task_no

        self._prompt_info_registrar.trace_start(trace_no=trace_no)

        self._trace_info_registrar.trace_start(
            trace_no=trace_no,
            thread_no=thread_no,
            task_no=task_no,
        )

    def trace_end(self, trace_no: TraceNo):
        self._trace_numbers_registrar.trace_end(trace_no=trace_no)
        self._prompt_info_registrar.trace_end(trace_no=trace_no)
        self._trace_info_registrar.trace_end(trace_no=trace_no)

    @contextmanager
    def trace_call(self, trace_no: TraceNo, trace_args: TraceArgs):

        self._prompt_info_registrar.trace_call_start(
            trace_no=trace_no, trace_args=trace_args
        )
        try:
            yield
        finally:
            self._prompt_info_registrar.trace_call_end(trace_no=trace_no)

    def prompt_start(
        self,
        trace_no: TraceNo,
        prompt_no: PromptNo,
        trace_args: TraceArgs,
        out: str,
    ) -> None:

        self._prompt_info_registrar.prompt_start(
            trace_no=trace_no,
            prompt_no=prompt_no,
            trace_args=trace_args,
            out=out,
        )

        self._add_module_to_trace.prompt_start(trace_args)

    def prompt_end(self, trace_no: TraceNo, prompt_no: PromptNo, command: str) -> None:
        self._prompt_info_registrar.prompt_end(
            trace_no=trace_no,
            prompt_no=prompt_no,
            command=command,
        )

    def stdout(self, task_or_thread: Task | Thread, line: str):
        trace_no = self._trace_no_map[task_or_thread]
        self._stdout_registrar.stdout(trace_no=trace_no, line=line)

    def __enter__(self):
        self._peek_stdout = peek_stdout_by_task_and_thread(
            to_peek=self._tasks_and_threads, callback=self.stdout
        )
        self._entering_thread = threading.current_thread()
        self._peek_stdout.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._peek_stdout.__exit__(exc_type, exc_value, traceback)
        self._thread_task_done_callback.close()
        if self._entering_thread:
            if trace_no := self._trace_no_map.get(self._entering_thread):
                self.trace_end(trace_no)
