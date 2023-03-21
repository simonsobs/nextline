import inspect
from logging import getLogger

from .call import sys_trace
from .plugin import build_hook
from .types import QueueIn, QueueOut, RunArg, RunResult


def run(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:

    logger = getLogger(__name__)

    hook = build_hook(run_arg=run_arg, queue_in=queue_in, queue_out=queue_out)

    with hook.with_.context():

        result = RunResult(ret=None, exc=None)

        try:
            func = hook.hook.compose_callable()
        except BaseException as exc:
            result.exc = exc
            return result

        trace_func = hook.hook.create_trace_func()

        try:
            with sys_trace(trace_func=trace_func):
                result.ret = func()
        except BaseException as exc:
            if exc.__traceback__:
                # remove this frame from the traceback.
                if exc.__traceback__.tb_frame is inspect.currentframe():
                    exc.__traceback__ = exc.__traceback__.tb_next
                else:
                    logger.warning('The first frame is not the current frame.')

            result.exc = exc

        hook.hook.finalize_run_result(run_result=result)

        return result
