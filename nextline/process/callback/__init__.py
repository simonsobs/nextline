from __future__ import annotations

import threading
from asyncio import Task
from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from threading import Thread
from typing import Dict, MutableMapping, Optional, Set
from weakref import WeakKeyDictionary

from apluggy import PluginManager

from nextline.count import PromptNoCounter, TraceNoCounter
from nextline.process.io import peek_stdout_by_task_and_thread
from nextline.process.types import CommandQueueMap
from nextline.types import RunNo, TraceNo
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
        modules_to_trace: Set[str],
        command_queue_map: CommandQueueMap,
    ):
        self._trace_no_counter = TraceNoCounter(1)
        self._prompt_no_counter = PromptNoCounter(1)
        self._command_queue_map = command_queue_map
        self._trace_no_map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()
        self._trace_args_map: Dict[TraceNo, TraceArgs] = {}
        self._trace_id_factory = ThreadTaskIdComposer()

        self._hook = PluginManager(spec.PROJECT_NAME)
        self._hook.add_hookspecs(spec)

        self._logger = getLogger(__name__)

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

    def task_or_thread_start(self) -> None:
        trace_no = self._trace_no_counter()
        self._hook.hook.task_or_thread_start(trace_no=trace_no)

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        self._hook.hook.task_or_thread_end(task_or_thread=task_or_thread)

    def trace_start(self, trace_no: TraceNo):
        thread_task_id = self._trace_id_factory()
        thread_no = thread_task_id.thread_no
        task_no = thread_task_id.task_no
        self._command_queue_map[trace_no] = Queue()

        self._hook.hook.trace_start(
            trace_no=trace_no, thread_no=thread_no, task_no=task_no
        )

    def trace_end(self, trace_no: TraceNo):
        self._hook.hook.trace_end(trace_no=trace_no)
        del self._command_queue_map[trace_no]

    @contextmanager
    def trace_call(self, trace_args: TraceArgs):
        trace_no = self._trace_no_map[current_task_or_thread()]
        self._trace_args_map[trace_no] = trace_args
        with self._hook.with_.trace_call(trace_no=trace_no, trace_args=trace_args):
            try:
                yield
            finally:
                del self._trace_args_map[trace_no]

    @contextmanager
    def cmdloop(self):
        trace_no = self._trace_no_map[current_task_or_thread()]
        trace_args = self._trace_args_map[trace_no]
        with self._hook.with_.cmdloop(trace_no=trace_no, trace_args=trace_args):
            yield

    def prompt(self, out: str) -> str:
        trace_no = self._trace_no_map[current_task_or_thread()]
        prompt_no = self._prompt_no_counter()
        self._logger.debug(f'PromptNo: {prompt_no}')
        trace_args = self._trace_args_map[trace_no]
        with (
            p := self._hook.with_.prompt(
                trace_no=trace_no, prompt_no=prompt_no, trace_args=trace_args, out=out
            )
        ):
            while True:
                command, prompt_no_, trace_no_ = self._command_queue_map[trace_no].get()
                try:
                    assert trace_no_ == trace_no
                except AssertionError:
                    msg = f'TraceNo mismatch: {trace_no_} != {trace_no}'
                    self._logger.exception(msg)
                    raise
                if prompt_no_ == prompt_no:
                    break
                self._logger.warning(f'PromptNo mismatch: {prompt_no_} != {prompt_no}')
            p.gen.send(command)
        return command

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
