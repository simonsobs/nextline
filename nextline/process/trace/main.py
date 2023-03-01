from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from nextline.process.pdb.proxy import PdbInterfaceTraceFuncFactory

from .wrap import (
    AddFirstModule,
    DispatchForThreadOrTask,
    Filter,
    FilterFirstModule,
    FromFactory,
)

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.run import TraceContext


def Trace(context: TraceContext) -> TraceFunc:
    '''Build the main system trace function of Nextline.'''

    modules_to_trace = context['modules_to_trace']

    factory = FactoryForThreadOrTask(context=context)

    trace = DispatchForThreadOrTask(factory=factory)
    trace = AddFirstModule(modules_to_trace=modules_to_trace, trace=trace)
    trace = Filter(trace=trace, filter=context['callback'].filter)

    return trace


def FactoryForThreadOrTask(context: TraceContext) -> Callable[[], TraceFunc]:
    '''Return a function that returns a trace function for a thread or asyncio task.'''

    modules_to_trace = context['modules_to_trace']
    factory = PdbInterfaceTraceFuncFactory(callback=context['callback'])

    def _trace_factory() -> TraceFunc:
        '''To be called in the thread or asyncio task to be traced.'''
        trace = FromFactory(factory=factory)
        trace = FilterFirstModule(trace=trace, modules_to_trace=modules_to_trace)
        return trace

    return _trace_factory
