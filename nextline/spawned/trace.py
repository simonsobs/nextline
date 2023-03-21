from logging import getLogger
from typing import Optional

from apluggy import PluginManager

from .types import TraceFunction


def TraceFunc(hook: PluginManager) -> TraceFunction:
    '''Return the trace function of Nextline to be set by sys.settrace().'''

    logger = getLogger(__name__)

    def _trace_func(frame, event, arg) -> Optional[TraceFunction]:
        try:
            return hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
        except BaseException:
            logger.exception('')
            raise

    return _trace_func
