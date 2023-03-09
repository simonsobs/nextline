from __future__ import annotations

from logging import getLogger
from types import FrameType
from typing import TYPE_CHECKING, Optional

from apluggy import PluginManager

from . import spec

if TYPE_CHECKING:
    from sys import TraceFunction  # type: ignore  # noqa: F401


assert spec.PROJECT_NAME  # used in the doctest


class TraceFunc:
    '''The trace function of Nextline to be set by sys.settrace().

    Python docs: sys.settrace():
    https://docs.python.org/3/library/sys.html#sys.settrace

    This class only calls a hook function. The actual trace function is
    implemented in plugins.

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

    def __init__(self, hook: PluginManager):
        self._hook = hook
        self._logger = getLogger(__name__)

    def __call__(self, frame: FrameType, event, arg) -> Optional[TraceFunction]:
        try:
            return self._hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
        except BaseException:
            self._logger.exception('')
            raise

    def __enter__(self):
        self._hook.hook.start()
        self._logger.info(f'{self.__class__.__name__}: started the hook')
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._hook.hook.close(
            exc_type=exc_type, exc_value=exc_value, traceback=traceback
        )
        self._logger.info(f'{self.__class__.__name__}: closed the hook')
