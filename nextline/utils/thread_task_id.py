from asyncio import Task, current_task
from collections import defaultdict
from threading import Thread, current_thread
from typing import Callable
from weakref import WeakKeyDictionary

from nextline.count import TaskNoCounter, ThreadNoCounter
from nextline.types import TaskNo, ThreadNo, ThreadTaskId


class ThreadTaskIdComposer:
    """Create ThreadTaskId objects with unique thread and async task numbers"""

    def __init__(self) -> None:
        self.thread_no_counter = ThreadNoCounter(1)

        self._map = WeakKeyDictionary[Thread | Task, ThreadTaskId]()
        self._thread_no_map = WeakKeyDictionary[Thread, ThreadNo]()
        self._task_no_map = WeakKeyDictionary[Task, TaskNo]()
        self._task_no_counter_map = defaultdict[ThreadNo, Callable[[], TaskNo]](
            lambda: TaskNoCounter(1)
        )

    def __call__(self) -> ThreadTaskId:
        """ThreadTaskId with the current thread and async task numbers

        Returns
        -------
        ThreadTaskId
            With the current thread and async task numbers. If not in an async
            task, the async task number will be None.
        """

        thread, task = self._current_thread_task()

        key = task or thread

        if ret := self._map.get(key):
            return ret

        ret = self._compose(thread, task)

        self._map[key] = ret

        return ret

    def has_id(self) -> bool:
        """True if the id has been created in the current thread and task"""
        thread, task = self._current_thread_task()
        key = task or thread
        return key in self._map

    def reset(self) -> None:
        """Start over the thread and async task numbers from one

        This method only resets the counters that generate thread and async
        task numbers. If the __call__() is executed in a thread and async task
        for which the ID has been generated before the reset, it will still
        return the same ID created before the reset.
        """
        self.thread_no_counter = ThreadNoCounter(1)
        self._task_no_counter_map.clear()

    def _current_thread_task(self) -> tuple[Thread, Task | None]:
        try:
            task = current_task()
        except RuntimeError:
            task = None
        return current_thread(), task

    def _compose(self, thread: Thread, task: Task | None) -> ThreadTaskId:
        thread_no = self._thread_no_map.get(thread)
        if not thread_no:
            thread_no = self.thread_no_counter()
            assert thread_no
            self._thread_no_map[thread] = thread_no

        if not task:
            return ThreadTaskId(thread_no=thread_no, task_no=None)

        task_no = self._task_no_map.get(task)
        if not task_no:
            task_no = self._task_no_counter_map[thread_no]()
            self._task_no_map[task] = task_no

        return ThreadTaskId(thread_no=thread_no, task_no=task_no)
