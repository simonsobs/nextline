import sys
import threading

from typing import Callable, Any, Type

from .types import TraceFunc

Func = Callable[[], Any]
DoneFunc = Callable[[Any, Type[Exception]], None]


def call_with_trace(
    func: Func,
    trace: TraceFunc,
    thread: bool = True,
) -> Any:
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
        provide args. A return value and an exception will be given to `done`.
    trace: callable
        A trace function.
    thread: bool, default True
        If False, no new threads will be traced.

    Returns
    -------
    any
        The return value of func().

    Raises
    ------
    any
        An exception raised in func(). The exception is re-raised after the
        original trace function is put back.
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
        if exc:
            raise exc
        return ret
