from __future__ import annotations

from asyncio import Task
from collections.abc import MutableSet, Set
from functools import lru_cache, partial
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, ContextManager, Iterable, Optional
from weakref import WeakKeyDictionary

from nextline.utils import current_task_or_thread, match_any

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


def FilterByModuleName(trace: TraceFunc, patterns: Iterable[str]) -> TraceFunc:
    '''Skip Python modules with names that match any of the patterns.'''

    patterns = frozenset(patterns)

    # NOTE: match_any() is slow
    match_any_ = lru_cache(partial(match_any, patterns=patterns))

    def filter(frame: FrameType, event, arg) -> bool:
        del event, arg
        module_name = frame.f_globals.get('__name__')
        return not match_any_(module_name)

    return Filter(trace=trace, filter=filter)


def FilterLambda(trace: TraceFunc) -> TraceFunc:
    '''Skip lambda functions.'''

    def filter(frame: FrameType, event, arg) -> bool:
        del event, arg
        func_name = frame.f_code.co_name
        return not func_name == '<lambda>'

    return Filter(trace=trace, filter=filter)


def Filter(
    trace: TraceFunc, filter: Callable[[FrameType, str, Any], bool]
) -> TraceFunc:
    '''Skip if the filter returns False.'''

    def _trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if filter(frame, event, arg):
            return trace(frame, event, arg)
        return None

    return _trace


def AddFirstModule(trace: TraceFunc, modules_to_trace: MutableSet[str]) -> TraceFunc:
    '''Add the module name to the set the first time traced in a module with a name.'''

    def callback(frame: FrameType, event, arg) -> bool:
        del event, arg
        if module_name := frame.f_globals.get('__name__'):
            # The module has a name.
            modules_to_trace.add(module_name)
            logger = getLogger(__name__)
            msg = f'{AddFirstModule.__name__}: added {module_name!r}'
            logger.info(msg)
            return True
        return False

    return CallbackUntilAccepted(trace=trace, callback=callback)


def CallbackUntilAccepted(
    trace: TraceFunc, callback: Callable[[FrameType, str, object], bool]
) -> TraceFunc:
    '''Call the callback when traced until the callback returns True.'''
    first = True

    def create_local_trace() -> TraceFunc:
        '''Return a trace function that executes the callback.'''
        next_trace: TraceFunc | None = trace

        def local_trace(frame, event, arg) -> Optional[TraceFunc]:
            '''Execute the callback.'''
            nonlocal first, next_trace
            assert next_trace

            accepted = callback(frame, event, arg)

            logger = getLogger(__name__)
            name = CallbackUntilAccepted.__name__
            msg = f'{name}: the callback returned {accepted!r}'
            logger.debug(msg)

            if accepted:
                # Stop executing the callback.
                first = False
                return next_trace(frame, event, arg)

            # Continue until the callback accepts.
            if next_trace := next_trace(frame, event, arg):
                return local_trace
            return None

        return local_trace

    def global_trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if not first:
            # The callback has already accepted.
            return trace(frame, event, arg)

        return create_local_trace()(frame, event, arg)

    return global_trace


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


def FilterFirstModule(trace: TraceFunc, modules_to_trace: Set[str]) -> TraceFunc:
    '''Start tracing from a module in the set.

    Skip modules until reaching a module in the set. Stop skipping afterward.
    '''

    first = True

    def filter(frame: FrameType, event, arg) -> bool:
        nonlocal first
        del event, arg

        if first:
            module_name = frame.f_globals.get('__name__')
            if not match_any(module_name, modules_to_trace):
                return False

            first = False

            logger = getLogger(__name__)
            name = FilterFirstModule.__name__
            msg = f'{name}: started tracing at {module_name!r}'
            logger.info(msg)

        return True

    return Filter(trace=trace, filter=filter)


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
