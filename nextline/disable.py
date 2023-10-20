import contextlib
import sys
from collections.abc import Iterator


@contextlib.contextmanager
def disable_trace() -> Iterator[None]:
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
