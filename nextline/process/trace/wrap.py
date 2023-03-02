from __future__ import annotations

from asyncio import Task
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, ContextManager, Optional
from weakref import WeakKeyDictionary

from nextline.utils import current_task_or_thread

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


def Filter(
    trace: TraceFunc, filter: Callable[[FrameType, str, Any], bool]
) -> TraceFunc:
    '''Skip if the filter returns False.'''

    def _trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if filter(frame, event, arg):
            return trace(frame, event, arg)
        return None

    return _trace


def DispatchForThreadOrTask(factory: Callable[[], TraceFunc]) -> TraceFunc:
    '''Create a new trace function for each thread or asyncio task.'''

    map: WeakKeyDictionary[Task | Thread, TraceFunc] = WeakKeyDictionary()

    def ret(frame, event, arg) -> Optional[TraceFunc]:
        key = current_task_or_thread()
        trace = map.get(key)
        if not trace:
            trace = factory()
            map[key] = trace
            logger = getLogger(__name__)
            msg = f'{DispatchForThreadOrTask.__name__}: created trace for {key}'
            logger.info(msg)
        return trace(frame, event, arg)

    return ret


def FromFactory(factory: Callable[[], TraceFunc]) -> TraceFunc:
    '''Create a trace function first time called.

    Used to defer the creation of the trace function until need to call it.
    '''
    trace: TraceFunc | None = None

    def global_trace(frame, event, arg) -> Optional[TraceFunc]:
        nonlocal trace
        trace = trace or factory()
        return trace(frame, event, arg)

    return global_trace


def WithContext(
    trace: TraceFunc, context: Callable[[FrameType, str, Any], ContextManager[None]]
) -> TraceFunc:
    def _create_local_trace() -> TraceFunc:
        next_trace: TraceFunc | None = trace

        def _local_trace(frame, event, arg) -> Optional[TraceFunc]:
            nonlocal next_trace
            assert next_trace
            with context(frame, event, arg):
                if next_trace := next_trace(frame, event, arg):
                    return _local_trace
                return None

        return _local_trace

    def _global_trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        return _create_local_trace()(frame, event, arg)

    return _global_trace
