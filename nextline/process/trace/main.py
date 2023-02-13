from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from nextline.process.pdb.proxy import PdbInterfaceTraceFuncFactory

from .wrap import (
    TraceAddFirstModule,
    TraceDispatchThreadOrTask,
    TraceFromFactory,
    TraceSelectFirstModule,
    TraceSkipLambda,
    TraceSkipModule,
)

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
    '''Build the main system trace function of Nextline.'''

    modules_to_trace = context['modules_to_trace']

    factory = TraceFactoryForThreadOrTask(context=context)

    trace = TraceDispatchThreadOrTask(factory=factory)
    trace = TraceAddFirstModule(modules_to_trace=modules_to_trace, trace=trace)
    trace = TraceSkipLambda(trace=trace)
    trace = TraceSkipModule(skip=MODULES_TO_SKIP, trace=trace)

    return trace


def TraceFactoryForThreadOrTask(context: TraceContext) -> Callable[[], TraceFunc]:
    '''Return a function that returns a trace function for a thread or asyncio task.'''

    modules_to_trace = context['modules_to_trace']
    factory = PdbInterfaceTraceFuncFactory(context=context)

    def _factory() -> TraceFunc:
        '''To be called in the thread or asyncio task to be traced.'''
        trace = TraceFromFactory(factory=factory)
        return TraceSelectFirstModule(trace=trace, modules_to_trace=modules_to_trace)

    return _factory
