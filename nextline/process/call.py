from __future__ import annotations

import sys
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable, Optional, Tuple, TypeVar

from nextline.process.trace import TraceSkipModule

if TYPE_CHECKING:
    from nextline.types import TraceFunc

T = TypeVar("T")


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
    trace_func = TraceSkipModule(trace_func, {contextmanager.__module__, __name__})
    sys.settrace(trace_func)

    try:
        yield
    finally:
        sys.settrace(trace_func_org)
        if thread:
            threading.settrace(trace_func_org)  # type: ignore


def call_with_trace(
    func: Callable[[], T | None],
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

    with sys_trace(trace, thread):
        try:
            ret = func()
        except BaseException as e:
            exc = e
    if exc:

        # How to print the exception in the same way as the interpreter.
        # import traceback
        # traceback.print_exception(type(exc), exc, exc.__traceback__)

        if exc.__traceback__:
            # remove this frame from the traceback.
            # Note: exc.__traceback__ is sys._getframe()
            exc.__traceback__ = exc.__traceback__.tb_next

    return ret, exc
