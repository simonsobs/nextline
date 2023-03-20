from __future__ import annotations

import sys
from pathlib import Path
from types import CodeType
from typing import Any, Callable

from . import script
from .call import sys_trace
from .plugin import build_hook
from .trace import TraceFunc
from .types import QueueIn, QueueOut, RunArg, RunResult
from .utils import to_canonic_path


def run_(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:

    result = RunResult(ret=None, exc=None)

    try:
        func = _compose_callable(run_arg)
    except BaseException as e:
        result.exc = e
        return result

    run_no = run_arg.run_no
    hook = build_hook(run_no=run_no, queue_in=queue_in, queue_out=queue_out)

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

    return result


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
    # Read as a str and compile it as Pdb does.
    # https://github.com/python/cpython/blob/v3.10.10/Lib/pdb.py#L1568-L1592
    statement = path.read_text()
    code = compile(statement, str(path), 'exec')
    sys.path.insert(0, str(path.parent))
    return script.compose(code)
