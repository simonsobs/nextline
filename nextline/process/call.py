from __future__ import annotations

import sys
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

from nextline.process.trace.wrap import FilterByModuleName

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


@contextmanager
def sys_trace(trace_func: TraceFunc, thread: Optional[bool] = True):
    '''Trace callables in the context and all threads created during the context.

    Notes
    -----
    All new threads created during the context are traced regardless of whether
    the threads are created by code in the context. If the thread option is
    false, no new threads will be traced.

    Example:

    >>> def trace_func(frame, event, arg):
    ...     # will be skipped in the doctest because of TraceSkipModule
    ...     return trace_func

    >>> def callable():
    ...     pass

    >>> with sys_trace(trace_func):
    ...     callable()

    '''
    trace_func_org = sys.gettrace()

    if thread:
        threading.settrace(trace_func)

    # Skip the context manager and this module otherwise they will be traced after
    # the yield is returned.
    trace_func = FilterByModuleName(trace_func, {contextmanager.__module__, __name__})
    sys.settrace(trace_func)

    try:
        yield
    finally:
        sys.settrace(trace_func_org)
        if thread:
            threading.settrace(trace_func_org)  # type: ignore
