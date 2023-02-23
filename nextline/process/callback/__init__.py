from __future__ import annotations

import threading
from asyncio import Task
from contextlib import contextmanager
from threading import Thread
from typing import Callable, MutableMapping, Optional, Set
from weakref import WeakKeyDictionary

from apluggy import PluginManager

from nextline.process.io import peek_stdout_by_task_and_thread
from nextline.types import PromptNo, RunNo, TraceNo
from nextline.utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)

from . import spec
from .plugins import (
    AddModuleToTrace,
    PromptInfoRegistrar,
    RegistrarProxy,
    StdoutRegistrar,
    TraceInfoRegistrar,
    TraceNumbersRegistrar,
    hookimpl,
)
from .types import TraceArgs


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

        self._hook = PluginManager(spec.PROJECT_NAME)
        self._hook.add_hookspecs(spec)

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


class PeekStdout:
    def __init__(self, callback: 'Callback') -> None:
        self._callback = callback
        self._tasks_and_threads: Set[Task | Thread] = set()

    @hookimpl
    def task_or_thread_start(self) -> None:
        task_or_thread = current_task_or_thread()
        self._tasks_and_threads.add(task_or_thread)

    @hookimpl
    def start(self) -> None:
        self._peek_stdout = peek_stdout_by_task_and_thread(
            to_peek=self._tasks_and_threads, callback=self._callback.stdout
        )
        self._peek_stdout.__enter__()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._peek_stdout.__exit__(exc_type, exc_value, traceback)


class Callback:
    def __init__(
        self,
        run_no: RunNo,
        registrar: RegistrarProxy,
        trace_no_counter: Callable[[], TraceNo],
        modules_to_trace: Set[str],
    ):
        self._trace_no_counter = trace_no_counter
        self._trace_no_map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()
        self._trace_id_factory = ThreadTaskIdComposer()

        self._hook = PluginManager(spec.PROJECT_NAME)
        self._hook.add_hookspecs(spec)

        stdout_registrar = StdoutRegistrar(run_no=run_no, registrar=registrar)
        add_module_to_trace = AddModuleToTrace(modules_to_trace)
        trace_info_registrar = TraceInfoRegistrar(run_no=run_no, registrar=registrar)
        prompt_info_registrar = PromptInfoRegistrar(run_no=run_no, registrar=registrar)
        trace_numbers_registrar = TraceNumbersRegistrar(registrar=registrar)
        peek_stdout = PeekStdout(self)
        trace_mapper = TaskOrThreadToTraceMapper(self, self._trace_no_map)

        self._hook.register(stdout_registrar, name='stdout')
        self._hook.register(add_module_to_trace, name='add_module_to_trace')
        self._hook.register(trace_info_registrar, name='trace_info')
        self._hook.register(prompt_info_registrar, name='prompt_info')
        self._hook.register(trace_numbers_registrar, name='trace_numbers')
        self._hook.register(peek_stdout, name='peek_stdout')
        self._hook.register(trace_mapper, name='task_or_thread_to_trace_mapper')

    def task_or_thread_start(self, trace_no: TraceNo) -> None:
        self._hook.hook.task_or_thread_start(trace_no=trace_no)

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        self._hook.hook.task_or_thread_end(task_or_thread=task_or_thread)

    def trace_start(self, trace_no: TraceNo):
        thread_task_id = self._trace_id_factory()
        thread_no = thread_task_id.thread_no
        task_no = thread_task_id.task_no

        self._hook.hook.trace_start(
            trace_no=trace_no, thread_no=thread_no, task_no=task_no
        )

    def trace_end(self, trace_no: TraceNo):
        self._hook.hook.trace_end(trace_no=trace_no)

    @contextmanager
    def trace_call(self, trace_no: TraceNo, trace_args: TraceArgs):
        with self._hook.with_.trace_call(trace_no=trace_no, trace_args=trace_args):
            yield

    @contextmanager
    def cmdloop(self, trace_no: TraceNo, trace_args: TraceArgs):
        with self._hook.with_.cmdloop(trace_no=trace_no, trace_args=trace_args):
            yield

    @contextmanager
    def prompt(
        self, trace_no: TraceNo, prompt_no: PromptNo, trace_args: TraceArgs, out: str
    ):
        with (
            p := self._hook.with_.prompt(
                trace_no=trace_no, prompt_no=prompt_no, trace_args=trace_args, out=out
            )
        ):
            # Yield twice: once to receive from send(), and once to exit.
            # https://stackoverflow.com/a/68304565/7309855
            command = yield
            p.gen.send(command)
            yield

    def stdout(self, task_or_thread: Task | Thread, line: str):
        trace_no = self._trace_no_map[task_or_thread]
        self._hook.hook.stdout(trace_no=trace_no, line=line)

    def start(self) -> None:
        self._hook.hook.start()

    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._hook.hook.close(
            exc_type=exc_type, exc_value=exc_value, traceback=traceback
        )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close(exc_type, exc_value, traceback)
