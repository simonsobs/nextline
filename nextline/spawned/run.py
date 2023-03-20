from __future__ import annotations

from pathlib import Path
import sys
from types import CodeType
from typing import Any, Callable

from nextline.types import RunNo

from . import script
from .call import sys_trace
from .plugin import build_hook
from .trace import TraceFunc
from .types import QueueIn, QueueOut, RunArg, RunResult
from .utils import to_canonic_path


def run_(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:
    try:
        func = _compose_callable(run_arg)
    except BaseException as e:
        return RunResult(ret=None, exc=e)

    run_no = run_arg.run_no
    return run_with_trace(run_no, func, queue_in, queue_out)


def _compose_callable(run_arg: RunArg) -> Callable[[], Any]:
    # TODO: Rewrite with a match statement for Python 3.10
    statement = run_arg.statement
    filename = run_arg.filename

    if isinstance(statement, str):
        if (path := Path(to_canonic_path(statement))).is_file():
            statement = path

    if isinstance(statement, str):
        assert filename is not None
        code = compile(statement, filename, 'exec')
        return script.compose(code)
    elif isinstance(statement, Path):
        return _from_path(statement)
    elif isinstance(statement, CodeType):
        return script.compose(statement)
    elif callable(statement):
        return statement
    else:
        raise TypeError(f'statement: {statement!r}')


def _from_path(path: Path) -> Callable[[], Any]:
    statement = path.read_text()
    code = compile(statement, str(path), 'exec')
    sys.path.insert(0, str(path.parent))
    return script.compose(code)


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
