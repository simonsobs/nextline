from __future__ import annotations

import threading
from asyncio import Task
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, MutableMapping, Optional
from weakref import WeakKeyDictionary, WeakSet

from apluggy import PluginManager

from nextline.count import TraceNoCounter
from nextline.process.trace.spec import hookimpl
from nextline.types import TaskNo, ThreadNo, TraceNo
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
    def __init__(self) -> None:
        self._set: WeakSet[Task | Thread] = WeakSet()
        self._counter = ThreadTaskIdComposer()
        self._callback = ThreadTaskDoneCallback(done=self._on_end)
        self._main_thread: Optional[Thread] = None
        self._to_end: Optional[Thread] = None
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def filtered(self) -> None:
        current = current_task_or_thread()
        if current not in self._set:
            self._on_start(current)
            self._set.add(current)

    def _on_start(self, current: Task | Thread) -> None:
        self._logger.info(f'{self.__class__.__name__}._on_start: {current}')
        if current is self._main_thread:
            self._to_end = self._main_thread
        else:
            self._callback.register(current)
        self._counter()  # increment the counter
        self._hook.hook.task_or_thread_start()

    def _on_end(self, ending: Task | Thread):
        # The "ending" is not the "current" unless it is the main thread.
        self._logger.info(f'{self.__class__.__name__}._on_end: {ending}')
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
    def __init__(self) -> None:
        self._map: MutableMapping[Task | Thread, TraceNo] = WeakKeyDictionary()
        self._counter = TraceNoCounter(1)
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def task_or_thread_start(self) -> None:
        trace_no = self._counter()
        self._logger.info(f'{self.__class__.__name__} start: trace_no={trace_no}')
        self._map[current_task_or_thread()] = trace_no
        self._hook.hook.trace_start(trace_no=trace_no)

    @hookimpl
    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._map[task_or_thread]
        self._hook.hook.trace_end(trace_no=trace_no)
        self._logger.info(f'{self.__class__.__name__} end: trace_no={trace_no}')

    @hookimpl
    def current_trace_no(self) -> Optional[TraceNo]:
        return self._map.get(current_task_or_thread())
