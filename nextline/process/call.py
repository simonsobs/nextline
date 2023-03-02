from __future__ import annotations

import sys
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional

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

    Define a trace function that prints the module and function name of each
    call, line, and return event.
    >>> def trace_func(frame, event, arg):
    ...     module_name = frame.f_globals.get('__name__')
    ...     func_name = frame.f_code.co_name
    ...     print(f'trace_func(): {module_name}.{func_name}() # {event}')
    ...     return trace_func

    Define a callable to trace.
    >>> def callable():
    ...     print('callable()')

    Trace the callable.
    >>> with sys_trace(trace_func):
    ...     callable()
    trace_func(): nextline.process.call.callable() # call
    trace_func(): nextline.process.call.callable() # line
    callable()
    trace_func(): nextline.process.call.callable() # return
    trace_func(): contextlib.__exit__() # call
    trace_func(): contextlib.__exit__() # line
    trace_func(): contextlib.__exit__() # line
    trace_func(): contextlib.__exit__() # line
    trace_func(): nextline.process.call.sys_trace() # call
    trace_func(): nextline.process.call.sys_trace() # line


    The callable is traced.

    However, as can be seen in the output, after the callable returns, the
    trace function continues to be called until sys.settrace(None) is called in
    the finally clause.

    '''
    trace_func_org = sys.gettrace()

    if thread:
        threading.settrace(trace_func)

    sys.settrace(trace_func)

    try:
        yield
    finally:
        sys.settrace(trace_func_org)
        if thread:
            threading.settrace(trace_func_org)  # type: ignore
