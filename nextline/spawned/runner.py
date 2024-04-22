import inspect
from types import FrameType
from typing import Optional

from apluggy import PluginManager

from .call import sys_trace
from .plugin import Hook
from .types import QueueIn, QueueOut, RunArg, RunResult


def run(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:
    hook = Hook(run_arg=run_arg, queue_in=queue_in, queue_out=queue_out)
    with hook.with_.context():
        result = _compile_and_run(hook=hook, run_arg=run_arg)
        return result


def _compile_and_run(hook: PluginManager, run_arg: RunArg) -> RunResult:
    try:
        func = hook.hook.compose_callable()
    except BaseException as exc:
        _remove_frame(exc=exc, frame=inspect.currentframe())
        hook.hook.clean_exception(exc=exc)
        return RunResult(exc=exc)
    trace_func = hook.hook.create_trace_func()
    try:
        with sys_trace(trace_func=trace_func, thread=run_arg.trace_threads):
            ret = func()
        return RunResult(ret=ret)
    except BaseException as exc:
        _remove_frame(exc=exc, frame=inspect.currentframe())
        hook.hook.clean_exception(exc=exc)
        return RunResult(exc=exc)


def _remove_frame(exc: BaseException, frame: Optional[FrameType]) -> None:
    if exc.__traceback__ and frame and exc.__traceback__.tb_frame is frame:
        exc.__traceback__ = exc.__traceback__.tb_next
