from __future__ import annotations

from asyncio import Task
from collections.abc import MutableSet, Set
from functools import lru_cache
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional
from weakref import WeakKeyDictionary

from nextline.process.pdb.proxy import PdbInterfaceTraceFuncFactory
from nextline.utils import current_task_or_thread, match_any

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.run import TraceContext


MODULES_TO_SKIP = {
    'multiprocessing.*',
    'threading',
    'queue',
    'importlib',
    'asyncio.*',
    'codec',
    'concurrent.futures.*',
    'selectors',
    'weakref',
    '_weakrefset',
    'socket',
    'logging',
    'os',
    'collections.*',
    'importlib.*',
    'pathlib',
    'typing',
    'posixpath',
    'fnmatch',
    '_pytest.*',
    'pluggy.*',
}


def Trace(context: TraceContext) -> TraceFunc:
    '''Create the main trace function.'''

    modules_to_trace = context['modules_to_trace']

    factory = TraceFactoryForThreadOrTask(context=context)

    trace = TraceDispatchThreadOrTask(factory=factory)
    trace = TraceAddFirstModule(modules_to_trace=modules_to_trace, trace=trace)
    trace = TraceSkipLambda(trace=trace)
    trace = TraceSkipModule(skip=MODULES_TO_SKIP, trace=trace)

    return trace


def TraceFactoryForThreadOrTask(context: TraceContext) -> Callable[[], TraceFunc]:

    modules_to_trace = context['modules_to_trace']
    factory = PdbInterfaceTraceFuncFactory(context=context)

    def _factory() -> TraceFunc:
        '''To be called in the thread or task to be traced.'''
        trace = TraceFromFactory(factory=factory)
        return TraceSelectFirstModule(trace=trace, modules_to_trace=modules_to_trace)

    return _factory


def TraceSkipModule(trace: TraceFunc, skip: Iterable[str]) -> TraceFunc:
    '''Traces functions from modules that are not in skip.'''
    skip = frozenset(skip)

    # NOTE: logger does not work in this trace function. If logger is used, the script
    # won't exit for unknown reasons.

    # logger = getLogger(__name__)

    @lru_cache
    def to_skip(module_name: str | None) -> bool:
        # NOTE: _is_matched_to_any() is slow
        return match_any(module_name, skip)

    def filter(frame: FrameType, event, arg) -> bool:
        del event, arg
        module_name = frame.f_globals.get('__name__')
        return not to_skip(module_name)

    return TraceFilter(trace=trace, filter=filter)


def TraceSkipLambda(trace: TraceFunc) -> TraceFunc:
    '''Traces functions that are not lambdas.'''

    def filter(frame: FrameType, event, arg) -> bool:
        del event, arg
        func_name = frame.f_code.co_name
        return not func_name == '<lambda>'

    return TraceFilter(trace=trace, filter=filter)


def TraceFilter(
    trace: TraceFunc, filter: Callable[[FrameType, str, Any], bool]
) -> TraceFunc:
    '''Trace only if the filter returns True.'''

    def _trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if filter(frame, event, arg):
            return trace(frame, event, arg)
        return None

    return _trace


def TraceAddFirstModule(
    trace: TraceFunc, modules_to_trace: MutableSet[str]
) -> TraceFunc:
    '''Add the module name to the set the first time traced in a module with a name.'''

    def callback(frame: FrameType, event, arg) -> bool:
        del event, arg
        if module_name := frame.f_globals.get('__name__'):
            # The module has a name.
            modules_to_trace.add(module_name)
            logger = getLogger(__name__)
            msg = f'{TraceAddFirstModule.__name__}: added {module_name!r}'
            logger.info(msg)
            return True
        return False

    return TraceCallbackUntilAccepted(trace=trace, callback=callback)


def TraceCallbackUntilAccepted(
    trace: TraceFunc, callback: Callable[[FrameType, str, object], bool]
) -> TraceFunc:
    '''Execute the callback when traced until the callback returns True.'''
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
            name = TraceCallbackUntilAccepted.__name__
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


def TraceDispatchThreadOrTask(factory: Callable[[], TraceFunc]) -> TraceFunc:
    '''Create a new trace function for each thread or asyncio task'''

    map: WeakKeyDictionary[Task | Thread, TraceFunc] = WeakKeyDictionary()

    def ret(frame, event, arg) -> Optional[TraceFunc]:
        key = current_task_or_thread()
        trace = map.get(key)
        if not trace:
            trace = factory()
            map[key] = trace
            logger = getLogger(__name__)
            msg = f'{TraceDispatchThreadOrTask.__name__}: created trace for {key}'
            logger.info(msg)
        return trace(frame, event, arg)

    return ret


def TraceSelectFirstModule(trace: TraceFunc, modules_to_trace: Set[str]) -> TraceFunc:
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
            name = TraceSelectFirstModule.__name__
            msg = f'{name}: started tracing at {module_name!r}'
            logger.info(msg)

        return True

    return TraceFilter(trace=trace, filter=filter)


def TraceFromFactory(factory: Callable[[], TraceFunc]) -> TraceFunc:
    '''Create a trace function first time called.

    Used to defer the creation of the trace function until need to call it.
    '''
    trace: TraceFunc | None = None

    def global_trace(frame, event, arg) -> Optional[TraceFunc]:
        nonlocal trace
        trace = trace or factory()
        return trace(frame, event, arg)

    return global_trace
