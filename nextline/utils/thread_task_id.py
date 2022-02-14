import threading
import asyncio
from itertools import count

from typing import Callable, Set, Dict, Optional, Union

from .types import ThreadID, TaskId, ThreadTaskId


##__________________________________________________________________||
class UniqThreadTaskIdComposer:
    """Compose paris of unique thread Id and async task Id"""

    def __init__(self):

        self.thread_id_counter = count(1).__next__

        self._map: Dict[
            Union[threading.Thread, asyncio.Task], ThreadTaskId
        ] = {}
        self._thread_id_map: Dict[threading.Thread, ThreadID] = {}
        self._task_id_counter_map: Dict[
            threading.Thread, Callable[[], int]
        ] = {}
        self._task_id_map: Dict[asyncio.Task, TaskId] = {}

    def __call__(self) -> ThreadTaskId:
        """Return the pair of the current thread ID and async task ID

        Returns
        -------
        tuple
            The pair of the current thread ID and async task ID. If
            not in an async task, the async task ID will be None.
        """

        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None

        thread = threading.current_thread()

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
