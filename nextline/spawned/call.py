import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from .types import TraceFunction


@contextmanager
def sys_trace(
    trace_func: TraceFunction, thread: Optional[bool] = True
) -> Iterator[None]:
    '''Trace callables in the context and all threads created during the context.

    Notes
    -----
    All new threads created during the context are traced regardless of whether
    the threads are created by code in the context. If the thread option is
    false, no new threads will be traced.

    Example:

    Define a trace function.
    >>> def trace_func(frame, event, arg):
    ...     # Print the module name, function name, and event.
    ...     module_name = frame.f_globals.get('__name__')
    ...     func_name = frame.f_code.co_name
    ...     print(f'trace_func(): {module_name}.{func_name}() # {event}')
    ...
    ...     # Return the trace function only if the function name is 'callable'.
    ...     if func_name == 'callable':
    ...         return trace_func
    ...     return None

    Define a callable to trace.
    >>> def callable():
    ...     print('callable()')

    Trace the callable.
    >>> with sys_trace(trace_func):
    ...     callable()
    trace_func(): nextline.spawned.call.callable() # call
    trace_func(): nextline.spawned.call.callable() # line
    callable()
    trace_func(): nextline.spawned.call.callable() # return
    trace_func(): contextlib.__exit__() # call
    trace_func(): nextline.spawned.call.sys_trace() # call


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
