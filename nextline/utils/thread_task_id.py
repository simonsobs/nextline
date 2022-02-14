from threading import Thread, current_thread
from asyncio import Task, current_task
from itertools import count
from collections import defaultdict
from weakref import WeakKeyDictionary

from typing import Union, Callable, Tuple, Dict, DefaultDict

from .types import ThreadID, TaskId, ThreadTaskId


class UniqThreadTaskIdComposer:
    """Compose paris of unique thread Id and async task Id"""

    def __init__(self):

        self.thread_id_counter = count(1).__next__

        self._map: Dict[
            Union[Thread, Task], ThreadTaskId
        ] = WeakKeyDictionary()

        self._thread_id_map: Dict[Thread, ThreadID] = WeakKeyDictionary()
        self._task_id_map: Dict[Task, TaskId] = WeakKeyDictionary()

        self._task_id_counter_map: DefaultDict[
            ThreadID, Callable[[], int]
        ] = defaultdict(lambda: count(1).__next__)

    def __call__(self) -> ThreadTaskId:
        """Return the pair of the current thread ID and async task ID

        Returns
        -------
        tuple
            The pair of the current thread ID and async task ID. If
            not in an async task, the async task ID will be None.
        """

        thread, task = self._current_thread_task()

        key = task or thread

        if ret := self._map.get(key):
            return ret

        ret = self._compose(thread, task)

        self._map[key] = ret

        return ret

    def _current_thread_task(self) -> Tuple[Thread, Union[Task, None]]:
        try:
            task = current_task()
        except RuntimeError:
            task = None
        return current_thread(), task

    def _compose(
        self, thread: Thread, task: Union[Task, None]
    ) -> ThreadTaskId:

        thread_id = self._thread_id_map.get(thread)
        if not thread_id:
            thread_id = self.thread_id_counter()
            self._thread_id_map[thread] = thread_id

        if not task:
            return thread_id, None

        task_id = self._task_id_map.get(task)
        if not task_id:
            task_id = self._task_id_counter_map[thread_id]()
            self._task_id_map[task] = task_id

        return thread_id, task_id
