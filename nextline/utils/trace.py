from threading import Thread, current_thread
from asyncio import Task, current_task
from weakref import WeakKeyDictionary

from typing import Optional, Union, Callable, Dict, Any
from types import FrameType

from ..types import TraceFunc


class TraceSingleThreadTask:
    """Dispatch a new trace function for each thread or asyncio task"""

    def __init__(self, factory: Callable[[], TraceFunc]):
        self._factory = factory
        self._map: Dict[Union[Thread, Task], TraceFunc] = WeakKeyDictionary()

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:

        key = self._current_task_or_thread()

        trace = self._map.get(key)
        if not trace:
            trace = self._factory()
            self._map[key] = trace

        return trace(frame, event, arg)

    def _current_task_or_thread(self) -> Union[Task, Thread]:
        try:
            task = current_task()
        except RuntimeError:
            task = None
        return task or current_thread()
