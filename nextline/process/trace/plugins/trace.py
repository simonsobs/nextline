from __future__ import annotations

import threading
from asyncio import Task
from contextlib import contextmanager
from logging import getLogger
from queue import Queue
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Callable, Dict, MutableMapping, Optional, Tuple
from weakref import WeakKeyDictionary, WeakSet

from apluggy import PluginManager

from nextline.count import PromptNoCounter, TraceNoCounter
from nextline.process.exc import TraceNotCalled
from nextline.process.pdb.proxy import TraceCallCallback, instantiate_pdb
from nextline.process.trace.spec import hookimpl
from nextline.process.trace.types import TraceArgs
from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, TaskNo, ThreadNo, TraceNo
from nextline.utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class CallbackForTrace:
    def __init__(
        self,
        trace_no: TraceNo,
        hook: PluginManager,
        command_queue_map: CommandQueueMap,
        prompt_no_counter: Callable[[], PromptNo],
    ):
        self._trace_no = trace_no
        self._hook = hook
        self._command_queue_map = command_queue_map
        self._prompt_no_counter = prompt_no_counter

        self._command_queue: Queue[Tuple[str, PromptNo, TraceNo]] = Queue()
        self._trace_args: TraceArgs | None = None

        self._logger = getLogger(__name__)

    def trace_start(self):
        self._command_queue_map[self._trace_no] = self._command_queue = Queue()

    def trace_end(self):
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


class LocalTraceFunc:
    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._hook = hook
        self._command_queue_map = command_queue_map
        self._prompt_no_counter = PromptNoCounter(1)

        self._callback_for_trace_map: Dict[TraceNo, CallbackForTrace] = {}

        self._local_trace_func_map: Dict[TraceNo, TraceFunc] = {}

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:
        callback_for_trace = CallbackForTrace(
            trace_no=trace_no,
            hook=self._hook,
            command_queue_map=self._command_queue_map,
            prompt_no_counter=self._prompt_no_counter,
        )
        self._callback_for_trace_map[trace_no] = callback_for_trace
        callback_for_trace.trace_start()

    @hookimpl
    def trace_end(self, trace_no: TraceNo) -> None:
        self._callback_for_trace_map[trace_no].trace_end()
        del self._callback_for_trace_map[trace_no]

    @hookimpl
    def local_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        local_trace_func = self._get_local_trace_func()
        return local_trace_func(frame, event, arg)

    def _get_local_trace_func(self) -> TraceFunc:
        trace_no = self._hook.hook.current_trace_no()
        local_trace_func = self._local_trace_func_map.get(trace_no)
        if local_trace_func is None:
            local_trace_func = self._create_local_trace_func(trace_no)
            self._local_trace_func_map[trace_no] = local_trace_func
        return local_trace_func

    def _create_local_trace_func(self, trace_no: TraceNo) -> TraceFunc:
        callback_for_trace = self._callback_for_trace_map[trace_no]

        trace = instantiate_pdb(callback=callback_for_trace)

        trace = TraceCallCallback(trace=trace, callback=callback_for_trace)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace


class TaskOrThreadToTraceMapper:
    @hookimpl
    def init(self, hook: PluginManager, command_queue_map: CommandQueueMap) -> None:
        self._trace_no_map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()
        self._hook = hook

        self._trace_id_factory = ThreadTaskIdComposer()
        self._trace_no_counter = TraceNoCounter(1)

        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self._task_or_thread_end
        )
        self._entering_thread: Optional[Thread] = None

        self._tasks_or_threads: WeakSet[Task | Thread] = WeakSet()

        self._logger = getLogger(__name__)

    @hookimpl
    def global_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if self._hook.hook.filter(trace_args=(frame, event, arg)):
            return None
        task_or_thread = current_task_or_thread()
        if task_or_thread not in self._tasks_or_threads:
            self._task_or_thread_start()
            self._tasks_or_threads.add(task_or_thread)
        return self._hook.hook.local_trace_func(frame=frame, event=event, arg=arg)

    def _task_or_thread_start(self) -> None:
        task_or_thread = current_task_or_thread()

        trace_no = self._trace_no_counter()
        self._trace_no_map[task_or_thread] = trace_no

        if task_or_thread is not self._entering_thread:
            self._thread_task_done_callback.register(task_or_thread)

        self._hook.hook.task_or_thread_start()

        self._trace_start(trace_no)

    def _task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self._trace_end(trace_no)
        self._hook.hook.task_or_thread_end(task_or_thread=task_or_thread)

    def _trace_start(self, trace_no: TraceNo):
        self._trace_id_factory()  # increment the thread and task numbers
        self._hook.hook.trace_start(trace_no=trace_no)

    def _trace_end(self, trace_no: TraceNo):
        self._hook.hook.trace_end(trace_no=trace_no)

    @hookimpl
    def current_thread_no(self) -> ThreadNo:
        thread_task_id = self._trace_id_factory()
        return thread_task_id.thread_no

    @hookimpl
    def current_task_no(self) -> Optional[TaskNo]:
        thread_task_id = self._trace_id_factory()
        return thread_task_id.task_no

    @hookimpl
    def current_trace_no(self) -> Optional[TraceNo]:
        task_or_thread = current_task_or_thread()
        return self._trace_no_map.get(task_or_thread)

    @hookimpl
    def start(self) -> None:
        self._entering_thread = threading.current_thread()

    @hookimpl
    def close(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._thread_task_done_callback.close()
        if self._entering_thread:
            if trace_no := self._trace_no_map.get(self._entering_thread):
                self._trace_end(trace_no)
