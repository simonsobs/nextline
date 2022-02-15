import threading
import asyncio
from weakref import WeakKeyDictionary

from typing import Union, Callable, Dict, Any, Optional
from types import FrameType

from ..types import TraceFunc


class TraceSingleThreadTask:
    """Dispatch a new trace function for each thread or asyncio task"""

    def __init__(self, wrapped_factory: Callable[[], TraceFunc]):

        self._wrapped_factory = wrapped_factory

        self._trace_map: Dict[
            Union[threading.Thread, asyncio.Task], TraceFunc
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

    def _current_task_or_thread(self) -> Union[threading.Thread, asyncio.Task]:
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        return task or threading.current_thread()
