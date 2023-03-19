from __future__ import annotations

from typing import Any, Callable

from nextline.types import RunNo

from . import script
from .call import sys_trace
from .plugin import build_hook
from .trace import TraceFunc
from .types import QueueIn, QueueOut, RunArg, RunResult


def run_(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:

    run_no = run_arg.run_no

    statement = run_arg.statement
    filename = run_arg.filename

    try:
        code = compile(statement, filename, 'exec')
    except BaseException as e:
        return RunResult(ret=None, exc=e)

    func = script.compose(code)

    return run_with_trace(run_no, func, queue_in, queue_out)


def run_with_trace(
    run_no: RunNo,
    func: Callable[[], Any],
    queue_in: QueueIn,
    queue_out: QueueOut,
) -> RunResult:

    ret: Any = None
    exc: BaseException | None = None

    hook = build_hook(run_no=run_no, queue_in=queue_in, queue_out=queue_out)

    with TraceFunc(hook=hook) as trace:
        with sys_trace(trace_func=trace):
            try:
                ret = func()
            except BaseException as e:
                exc = e

    # NOTE: How to print the exception in the same way as the interpreter.
    # import traceback
    # traceback.print_exception(type(exc), exc, exc.__traceback__)

    if exc and exc.__traceback__:
        # remove this frame from the traceback.
        # Note: exc.__traceback__ is sys._getframe()
        exc.__traceback__ = exc.__traceback__.tb_next

    return RunResult(ret=ret, exc=exc)
