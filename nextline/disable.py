import contextlib
import sys


@contextlib.contextmanager
def disable_trace():
    '''Remove the system trace function temporarily.
    
    Example:
    
    >>> with disable_trace():
    ...     # code without tracing
    ...     pass

    '''
    trace = sys.gettrace()
    sys.settrace(None)
    try:
        yield
    finally:
        sys.settrace(trace)
