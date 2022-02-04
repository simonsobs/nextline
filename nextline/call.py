import sys
import threading
from functools import partial

from typing import Callable, Any, Optional, Type
from types import FrameType


##__________________________________________________________________||
def exec_with_trace(code, trace, done=None):
    """Set the trace funciton while running the code

    Parameters
    ----------
    code : object
        A code to be executed. This must be an object that can be
        executed by the Python built-in Function exec().
    trace: callable
        A trace function.
    done: callable, optional
        A callable with two arguments. It will to be called after the
        code exits. The first argument is the return value, which is
        always None in the current implementation, because the
        built-in function exec() returns None. The second argument is
        the exception if an exception occurs or otherwise None.
    """

    globals_ = {"__name__": __name__}
    # To be given to exec() in order to address the issue
    # https://github.com/simonsobs/nextline/issues/7
    # __name__ is used in modules_to_trace in Trace.

    func = partial(exec, code, globals_)

    call_with_trace(func, trace, done)


Func = Callable[[], Any]

TraceFunc = Callable[
    [FrameType, str, Any], Optional[Callable[[FrameType, str, Any], Any]]
]
# Copied from (because not sure how to import)
# https://github.com/python/typeshed/blob/b88a6f19cdcf/stdlib/sys.pyi#L245

DoneFunc = Optional[Callable[[Any, Type[Exception]], None]]


def call_with_trace(
    func: Func, trace: TraceFunc, done: DoneFunc = None
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


##__________________________________________________________________||
