import threading
from asyncio import Task
from collections.abc import Iterator
from logging import getLogger
from threading import Thread
from typing import Optional
from weakref import WeakKeyDictionary, WeakSet

from apluggy import PluginManager, contextmanager

from nextline.count import TraceNoCounter
from nextline.spawned.plugin.spec import hookimpl
from nextline.types import TaskNo, ThreadNo, TraceNo
from nextline.utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)


class TaskAndThreadKeeper:
    def __init__(self) -> None:
        self._set = WeakSet[Task | Thread]()
        self._counter = ThreadTaskIdComposer()
        self._main_thread: Optional[Thread] = None
        self._to_end: Optional[Thread] = None
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    @contextmanager
    def context(self) -> Iterator[None]:
        self._callback = ThreadTaskDoneCallback(done=self._on_end)
        self._main_thread = threading.current_thread()
        try:
            yield
        finally:
            self._callback.close()
            if self._to_end:
                self._on_end(self._to_end)

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
        self._hook.hook.on_start_task_or_thread()

    def _on_end(self, ending: Task | Thread) -> None:
        # The "ending" is not the "current" unless it is the main thread.
        self._logger.info(f'{self.__class__.__name__}._on_end: {ending}')
        self._hook.hook.on_end_task_or_thread(task_or_thread=ending)

    @hookimpl
    def current_thread_no(self) -> ThreadNo:
        return self._counter().thread_no

    @hookimpl
    def current_task_no(self) -> Optional[TaskNo]:
        return self._counter().task_no


class TaskOrThreadToTraceMapper:
    def __init__(self) -> None:
        self._map = WeakKeyDictionary[Task | Thread, TraceNo]()
        self._counter = TraceNoCounter(1)
        self._logger = getLogger(__name__)

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    def on_start_task_or_thread(self) -> None:
        trace_no = self._counter()
        self._logger.info(f'{self.__class__.__name__} start: trace_no={trace_no}')
        self._map[current_task_or_thread()] = trace_no
        self._hook.hook.on_start_trace(trace_no=trace_no)

    @hookimpl
    def on_end_task_or_thread(self, task_or_thread: Task | Thread) -> None:
        trace_no = self._map[task_or_thread]
        self._hook.hook.on_end_trace(trace_no=trace_no)
        self._logger.info(f'{self.__class__.__name__} end: trace_no={trace_no}')

    @hookimpl
    def current_trace_no(self) -> Optional[TraceNo]:
        return self._map.get(current_task_or_thread())
