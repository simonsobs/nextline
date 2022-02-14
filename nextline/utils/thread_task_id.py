from threading import Thread, current_thread
from asyncio import Task, current_task
from itertools import count
from weakref import WeakKeyDictionary

from typing import Callable, Set, Dict, Optional, Union

from .types import ThreadID, TaskId, ThreadTaskId


##__________________________________________________________________||
class UniqThreadTaskIdComposer:
    """Compose paris of unique thread Id and async task Id"""

    def __init__(self):

        self.thread_id_counter = count(1).__next__

        self._map: Dict[
            Union[Thread, Task], ThreadTaskId
        ] = WeakKeyDictionary()
        self._thread_id_map: Dict[Thread, ThreadID] = WeakKeyDictionary()
        self._task_id_map: Dict[Task, TaskId] = WeakKeyDictionary()
        self._task_id_counter_map: Dict[Thread, Callable[[], int]] = {}

    def __call__(self) -> ThreadTaskId:
        """Return the pair of the current thread ID and async task ID

        Returns
        -------
        tuple
            The pair of the current thread ID and async task ID. If
            not in an async task, the async task ID will be None.
        """

        try:
            task = current_task()
        except RuntimeError:
            task = None

        thread = current_thread()

        key = task or thread

        ret = self._map.get(key)
        if ret:
            return ret

        ret = self._create_id(thread, task)

        self._map[key] = ret

        return ret

    def _create_id(self, thread, task) -> ThreadTaskId:

        thread_id = self._thread_id_map.get(thread)

        if not thread_id:
            thread_id = self.thread_id_counter()
            self._thread_id_map[thread] = thread_id
            self._task_id_counter_map[thread_id] = count(1).__next__

        if not task:
            return thread_id, None

        task_id = self._task_id_map.get(task)

        if not task_id:
            task_id = self._task_id_counter_map[thread_id]()
            self._task_id_map[task] = task_id

        return thread_id, task_id


##__________________________________________________________________||
