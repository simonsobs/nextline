import sys
import threading

from typing import Callable, Any, Optional, Type

from .types import TraceFunc

Func = Callable[[], Any]
DoneFunc = Callable[[Any, Type[Exception]], None]


def call_with_trace(
    func: Func, trace: TraceFunc, done: Optional[DoneFunc] = None
) -> None:
    """Set the trace funciton while running the funciton

    Notes
    -----
    The trace funciton will be used in all new threads created during
    the funciton execution regardless of whether the threads are
    creted by the funciton.

    Parameters
    ----------
    func : callable
        A fucntion to be called without any args. Use
        functools.partial to provide args. A return value and an
        exception will be given to `done`.
    trace: callable
        A trace function.
    done: callable, optional
        A callable with two arguments. It will to be called after the
        func exits. The first argument is the return value. The second
        argument is the exception if an exception occurs or otherwise
        None.
    """

    ret = None
    exc = None

    trace_org = sys.gettrace()
    threading.settrace(trace)
    sys.settrace(trace)
    try:
        ret = func()
    except BaseException as e:
        exc = e
    finally:
        sys.settrace(trace_org)
        threading.settrace(trace_org)
        if done:
            done(ret, exc)
