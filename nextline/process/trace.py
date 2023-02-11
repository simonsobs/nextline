from __future__ import annotations

import fnmatch
from asyncio import Task
from collections.abc import MutableSet, Set
from functools import lru_cache
from logging import getLogger
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Callable, Iterable, Optional
from weakref import WeakKeyDictionary

from nextline.utils import current_task_or_thread

from .pdb.proxy import PdbInterfaceTraceFuncFactory

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from .run import TraceContext


MODULES_TO_SKIP = {
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

    create_trace_for_single_thread_or_task = TraceFactoryForThreadOrTask(
        context=context
    )

    trace = TraceDispatchThreadOrTask(factory=create_trace_for_single_thread_or_task)
    trace = TraceAddFirstModule(modules_to_trace=modules_to_trace, trace=trace)
    trace = TraceSkipLambda(trace=trace)
    trace = TraceSkipModule(skip=MODULES_TO_SKIP, trace=trace)

    return trace


def TraceFactoryForThreadOrTask(context: TraceContext) -> Callable[[], TraceFunc]:

    modules_to_trace = context['modules_to_trace']
    trace_func_factory = PdbInterfaceTraceFuncFactory(context=context)

    def _factory():
        '''To be called in the thread or task to be traced.'''
        trace_call_pdb = TraceFromFactory(factory=trace_func_factory)
        return TraceSelectFirstModule(
            trace=trace_call_pdb,
            modules_to_trace=modules_to_trace,
        )

    return _factory


def TraceSkipModule(trace: TraceFunc, skip: Iterable[str]) -> TraceFunc:
    '''Traces functions from modules that are not in skip.'''
    skip = frozenset(skip)

    @lru_cache
    def to_skip(module_name: str | None) -> bool:
        # NOTE: _is_matched_to_any() is slow
        return _is_matched_to_any(module_name, skip)

    def ret(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        module_name = frame.f_globals.get('__name__')
        if to_skip(module_name):
            return None
        return trace(frame, event, arg)

    return ret


def TraceSkipLambda(trace: TraceFunc) -> TraceFunc:
    '''Traces functions that are not lambdas.'''

    def ret(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        func_name = frame.f_code.co_name
        if func_name == '<lambda>':
            return None
        return trace(frame, event, arg)

    return ret


def TraceAddFirstModule(
    trace: TraceFunc, modules_to_trace: MutableSet[str]
) -> TraceFunc:
    '''Add the module name to the set the first time traced in a module with a name.'''
    first = True
    logger = getLogger(__name__)

    def global_trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if not first:
            # The module name has already been added.
            return trace(frame, event, arg)

        def create_local_trace() -> TraceFunc:
            '''Return a trace function that adds the module name to the set.'''
            next_trace: TraceFunc | None = trace

            def local_trace(frame, event, arg) -> Optional[TraceFunc]:
                '''Add the module name to the set.'''
                nonlocal first, next_trace
                assert next_trace

                if module_name := frame.f_globals.get('__name__'):
                    # The module does have a name.
                    first = False
                    modules_to_trace.add(module_name)
                    msg = f'{TraceAddFirstModule.__name__}: added {module_name!r}'
                    logger.info(msg)
                    return next_trace(frame, event, arg)

                # Continue until called in a module with a name.
                if next_trace := next_trace(frame, event, arg):
                    return local_trace
                return None

            return local_trace

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

    In other words, skip modules until reaching one of modules in the set. Stop
    skipping afterward.
    '''
    first = True

    def ret(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        nonlocal first
        if first:
            module_name = frame.f_globals.get('__name__')
            if not _is_matched_to_any(module_name, modules_to_trace):
                return None
            first = False
            logger = getLogger(__name__)
            name = TraceSelectFirstModule.__name__
            msg = f'{name}: started tracing at {module_name!r}'
            logger.info(msg)
        return trace(frame, event, arg)

    return ret


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


def _is_matched_to_any(word: str | None, patterns: Iterable[str]) -> bool:
    '''Test if the word matches any of the patterns

    This function is based on Bdb.is_skipped_module():
    https://github.com/python/cpython/blob/v3.9.5/Lib/bdb.py#L191
    '''
    if word is None:
        return False
    for pattern in patterns:
        if fnmatch.fnmatch(word, pattern):
            return True
    return False
