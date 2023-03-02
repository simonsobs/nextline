from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from nextline.process.callback import Callback
from nextline.process.pdb.proxy import PdbInterfaceTraceFuncFactory

from .wrap import DispatchForThreadOrTask, Filter, FromFactory

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


def Trace(callback: Callback) -> TraceFunc:
    '''Build the main system trace function of Nextline.'''

    factory = FactoryForThreadOrTask(callback=callback)

    trace = DispatchForThreadOrTask(factory=factory)
    trace = Filter(trace=trace, filter=callback.filter)

    return trace


def FactoryForThreadOrTask(callback: Callback) -> Callable[[], TraceFunc]:
    '''Return a function that returns a trace function for a thread or asyncio task.'''

    factory = PdbInterfaceTraceFuncFactory(callback=callback)

    def _trace_factory() -> TraceFunc:
        '''To be called in the thread or asyncio task to be traced.'''
        trace = FromFactory(factory=factory)
        return trace

    return _trace_factory
