import inspect
from logging import getLogger
from typing import Optional

from .call import sys_trace
from .plugin import build_hook
from .types import QueueIn, QueueOut, RunArg, RunResult, TraceFunction
from .utils import WithContext


def run_(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:

    logger = getLogger(__name__)

    hook = build_hook(run_arg=run_arg, queue_in=queue_in, queue_out=queue_out)

    with hook.with_.context():

        result = RunResult(ret=None, exc=None)

        try:
            func = hook.hook.compose_callable()
        except BaseException as e:
            result.exc = e
            return result

        def trace_func(frame, event, arg) -> Optional[TraceFunction]:
            try:
                return hook.hook.global_trace_func(frame=frame, event=event, arg=arg)
            except BaseException:
                logger.exception('')
                raise

        with sys_trace(trace_func=trace_func):
            try:
                result.ret = func()
            except BaseException as e:
                result.exc = e

        exc = result.exc
        if exc and exc.__traceback__:
            # remove this frame from the traceback.
            if exc.__traceback__.tb_frame is inspect.currentframe():
                exc.__traceback__ = exc.__traceback__.tb_next
            else:
                logger.warning('The first frame is not the current frame.')

        if exc and exc.__traceback__ and isinstance(exc, KeyboardInterrupt):
            tb = exc.__traceback__
            while tb.tb_next:
                module = tb.tb_next.tb_frame.f_globals.get('__name__')
                if module == WithContext.__module__:
                    tb.tb_next = None
                    break
                tb = tb.tb_next

        return result
