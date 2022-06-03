from __future__ import annotations

import sys
import threading

from typing import Callable, Optional, Tuple, TypeVar

from .types import TraceFunc

T = TypeVar("T")


def call_with_trace(
    func: Callable[[], T],
    trace: TraceFunc,
    thread: Optional[bool] = True,
) -> Tuple[T | None, BaseException | None]:
    """Set the trace function while running the function

    Notes
    -----
    The trace function will be used in all new threads created during the
    function execution regardless of whether the threads are created by the
    function. If the thread option is false, the trace function will not be use
    in any new threads.

    Parameters
    ----------
    func : callable
        A function to be called without any args. Use functools.partial to
        provide args.
    trace: callable
        A trace function.
    thread: bool, default True
        If False, no new threads will be traced.

    Returns
    -------
    tuple
        A tuple with two elements. The first is the return value of func() or
        None if an exception is raised in func(). The second is the exception
        raised in func() or None if no exception is rased.

    """

    ret = None
    exc = None

    trace_org = sys.gettrace()
    if thread:
        threading.settrace(trace)
    sys.settrace(trace)
    try:
        ret = func()
    except BaseException as e:
        exc = e
    finally:
        sys.settrace(trace_org)
        if thread:
            threading.settrace(trace_org)  # type: ignore
        return ret, exc
