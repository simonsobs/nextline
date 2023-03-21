from .call import sys_trace
from .plugin import build_hook
from .trace import TraceFunc
from .types import QueueIn, QueueOut, RunArg, RunResult
from .utils import WithContext


def run_(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:

    result = RunResult(ret=None, exc=None)

    hook = build_hook(run_arg=run_arg, queue_in=queue_in, queue_out=queue_out)

    try:
        func = hook.hook.compose_callable()
    except BaseException as e:
        result.exc = e
        return result

    with TraceFunc(hook=hook) as trace:
        with sys_trace(trace_func=trace):
            try:
                result.ret = func()
            except BaseException as e:
                result.exc = e

    # NOTE: How to print the exception in the same way as the interpreter.
    # import traceback
    # traceback.print_exception(type(exc), exc, exc.__traceback__)

    exc = result.exc
    if exc and exc.__traceback__:
        # remove this frame from the traceback.
        # Note: exc.__traceback__ is sys._getframe()
        exc.__traceback__ = exc.__traceback__.tb_next

    if exc and exc.__traceback__ and isinstance(exc, KeyboardInterrupt):
        tb = exc.__traceback__
        while tb.tb_next:
            module = tb.tb_next.tb_frame.f_globals.get('__name__')
            if module == WithContext.__module__:
                tb.tb_next = None
                break
            tb = tb.tb_next

    return result
