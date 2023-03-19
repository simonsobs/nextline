from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from logging import getLogger
from types import CodeType
from typing import Any, Callable, TypeVar

from nextline.types import RunNo

from . import script
from .call import sys_trace
from .commands import PdbCommand
from .plugin import build_hook
from .trace import TraceFunc
from .types import CommandQueueMap, QueueIn, QueueOut, RunArg, RunResult

_T = TypeVar('_T')


def run_(run_arg: RunArg, queue_in: QueueIn, queue_out: QueueOut) -> RunResult:

    run_no = run_arg['run_no']

    statement = run_arg['statement']
    filename = run_arg['filename']

    try:
        code = _compile(statement, filename)
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

    with _trace(run_no, queue_in, queue_out) as trace:
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


@contextmanager
def _trace(run_no: RunNo, queue_in: QueueIn, queue_out: QueueOut):

    command_queue_map: CommandQueueMap = {}

    hook = build_hook(
        run_no=run_no,
        command_queue_map=command_queue_map,
        queue_in=queue_in,
        queue_out=queue_out,
    )

    with TraceFunc(hook=hook) as trace_func:
        with relay_commands(queue_in, command_queue_map):
            yield trace_func


def _compile(code: CodeType | str, filename: str) -> CodeType:
    if isinstance(code, str):
        return compile(code, filename, 'exec')
    return code


@contextmanager
def relay_commands(queue_in: QueueIn, command_queue_map: CommandQueueMap):
    '''Pass the Pdb commands from the main process to the Pdb instances.'''
    logger = getLogger(__name__)

    def fn() -> None:
        assert queue_in
        while msg := queue_in.get():
            logger.debug(f'queue_in.get() -> {msg!r}')
            if isinstance(msg, PdbCommand):
                command_queue_map[msg.trace_no].put(
                    (msg.command, msg.prompt_no, msg.trace_no)
                )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(try_again_on_error, fn)  # type: ignore
        try:
            yield
        finally:
            queue_in.put(None)  # type: ignore
            future.result()


def try_again_on_error(func: Callable[[], _T]) -> _T:
    '''Keep trying until the function succeeds without an exception.'''
    while True:
        try:
            return func()
        # except KeyboardInterrupt:
        #     raise
        except BaseException:
            logger = getLogger(__name__)
            logger.exception('')
