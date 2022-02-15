from threading import Thread, current_thread
from asyncio import Task, current_task
from weakref import WeakKeyDictionary

from typing import Optional, Union, Callable, Dict, Any
from types import FrameType

from ..types import TraceFunc


class TraceSingleThreadTask:
    """Dispatch a new trace function for each thread or asyncio task"""

    def __init__(self, wrapped_factory: Callable[[], TraceFunc]):

        self._wrapped_factory = wrapped_factory

        self._trace_map: Dict[
            Union[Thread, Task], TraceFunc
        ] = WeakKeyDictionary()

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:

        key = self._current_task_or_thread()

        trace = self._trace_map.get(key)
        if not trace:
            trace = self._wrapped_factory()
            self._trace_map[key] = trace

        return trace(frame, event, arg)

    def _current_task_or_thread(self) -> Union[Thread, Task]:
        try:
            task = current_task()
        except RuntimeError:
            task = None
        return task or current_thread()
