from __future__ import annotations

from typing import TYPE_CHECKING

from .wrap import DispatchForThreadOrTask, Filter


if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.callback import Callback


def Trace(callback: Callback) -> TraceFunc:
    '''Build the main system trace function of Nextline.'''

    factory = callback.factory

    trace = DispatchForThreadOrTask(factory=factory)
    trace = Filter(trace=trace, filter=callback.filter)

    return trace
