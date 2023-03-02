from __future__ import annotations

from typing import TYPE_CHECKING

from nextline.process.callback import Callback
from nextline.process.pdb.proxy import PdbInterfaceTraceFuncFactory

from .wrap import DispatchForThreadOrTask, Filter

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


def Trace(callback: Callback) -> TraceFunc:
    '''Build the main system trace function of Nextline.'''

    factory = PdbInterfaceTraceFuncFactory(callback=callback)

    trace = DispatchForThreadOrTask(factory=factory)
    trace = Filter(trace=trace, filter=callback.filter)

    return trace
