from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Iterator, Optional

from apluggy import PluginManager, contextmanager

from .plugin import spec

if TYPE_CHECKING:
    from sys import TraceFunction  # type: ignore  # noqa: F401


assert spec.PROJECT_NAME  # used in the doctest


@contextmanager
def TraceFunc(hook: PluginManager) -> Iterator[TraceFunction]:
    '''Yield the trace function of Nextline to be set by sys.settrace().

    Python docs: sys.settrace():
    https://docs.python.org/3/library/sys.html#sys.settrace

    This yielded function only calls a hook function. The actual trace function
    is implemented in plugins.

    Example:

    Save the original trace function.
    >>> import sys
    >>> trace_org = sys.gettrace()

    Initialize a plugin manager of apluggy.
    >>> hook = PluginManager(spec.PROJECT_NAME)
    >>> hook.add_hookspecs(spec)

    >>> # In practice, plugins are registered here.

    Enter the "with" block:
    >>> with TraceFunc(hook) as trace_func:
    ...
    ...     # Set the trace function.
    ...     sys.settrace(trace_func)
    ...
    ...     # run the Nextline client function here
    ...
    ...     # Unset the trace function.
    ...     sys.settrace(trace_org)

    '''

    logger = getLogger(__name__)

    def _trace_func(frame, event, arg) -> Optional[TraceFunction]:
        try:
            return hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
        except BaseException:
            logger.exception('')
            raise

    with hook.with_.context():
        logger.info(f'{TraceFunc.__name__}: started the hook')
        try:
            yield _trace_func
        finally:
            logger.info(f'{TraceFunc.__name__}: closing the hook')
