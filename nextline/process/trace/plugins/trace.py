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


class GlobalTraceFunc:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def global_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if self._hook.hook.filter(trace_args=(frame, event, arg)):
            return None
        self._hook.hook.filtered(trace_args=(frame, event, arg))
        return self._hook.hook.local_trace_func(frame=frame, event=event, arg=arg)


class TaskAndThreadKeeper:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

        self._counter = ThreadTaskIdComposer()
        self._callback = ThreadTaskDoneCallback(done=self._on_end)

        self._main_thread: Optional[Thread] = None
        self._to_end: Optional[Thread] = None

        self._set: WeakSet[Task | Thread] = WeakSet()

        self._logger = getLogger(__name__)

    @hookimpl
    def filtered(self) -> None:
        current = current_task_or_thread()
        if current not in self._set:
            self._on_start(current)
            self._set.add(current)

    def _on_start(self, current: Task | Thread) -> None:

        if current is self._main_thread:
            self._to_end = self._main_thread
        else:
            self._callback.register(current)

        self._counter()  # increment the counter

        self._hook.hook.task_or_thread_start()

    def _on_end(self, ending: Task | Thread):
        # The "ending" is not the "current" unless it is the main thread.
        self._hook.hook.task_or_thread_end(task_or_thread=ending)

    @hookimpl
    def current_thread_no(self) -> ThreadNo:
        return self._counter().thread_no

    @hookimpl
    def current_task_no(self) -> Optional[TaskNo]:
        return self._counter().task_no

    @hookimpl
    def start(self) -> None:
        self._main_thread = threading.current_thread()

    @hookimpl
    def close(self) -> None:
        self._callback.close()
        self._to_end and self._on_end(self._to_end)


class TaskOrThreadToTraceMapper:
    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

        self._trace_no_map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()
        self._trace_no_counter = TraceNoCounter(1)
        self._logger = getLogger(__name__)

    @hookimpl
    def task_or_thread_start(self) -> None:
        task_or_thread = current_task_or_thread()
        trace_no = self._trace_no_counter()
        self._trace_no_map[task_or_thread] = trace_no
        self._trace_start(trace_no)

    @hookimpl
    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self._trace_end(trace_no)

    def _trace_start(self, trace_no: TraceNo):
        self._hook.hook.trace_start(trace_no=trace_no)

    def _trace_end(self, trace_no: TraceNo):
        self._hook.hook.trace_end(trace_no=trace_no)

    @hookimpl
    def current_trace_no(self) -> Optional[TraceNo]:
        task_or_thread = current_task_or_thread()
        return self._trace_no_map.get(task_or_thread)


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
