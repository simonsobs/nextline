from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from logging import getLogger
from types import CodeType
from typing import Any, Callable, Set, TypedDict, TypeVar

from nextline.types import RunNo

from . import script
from .call import sys_trace
from .callback import Callback, RegistrarProxy
from .trace import Trace
from .types import QueueCommands, QueueRegistry, RunArg, RunResult, CommandQueueMap

_T = TypeVar('_T')


class TraceContext(TypedDict):
    callback: Callback
    modules_to_trace: Set[str]


def run_(
    run_arg: RunArg, q_commands: QueueCommands, q_registry: QueueRegistry
) -> RunResult:

    run_no = run_arg['run_no']

    statement = run_arg['statement']
    filename = run_arg['filename']

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        return RunResult(ret=None, exc=e)

    func = script.compose(code)

    return run_with_trace(run_no, func, q_commands, q_registry)


def run_with_trace(
    run_no: RunNo,
    func: Callable[[], Any],
    q_commands: QueueCommands,
    q_registry: QueueRegistry,
) -> RunResult:

    ret: Any = None
    exc: BaseException | None = None

    with _trace(run_no, q_commands, q_registry) as trace:
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
def _trace(run_no: RunNo, q_commands: QueueCommands, q_registry: QueueRegistry):

    command_queue_map: CommandQueueMap = {}
    modules_to_trace: Set[str] = set()

    with Callback(
        run_no=run_no,
        registrar=RegistrarProxy(q_registry),
        modules_to_trace=modules_to_trace,
        command_queue_map=command_queue_map,
    ) as callback:

        context = TraceContext(
            callback=callback,
            modules_to_trace=modules_to_trace,
        )

        trace = Trace(context=context)

        with relay_commands(q_commands, command_queue_map):
            yield trace


def _compile(code: CodeType | str, filename: str) -> CodeType:
    if isinstance(code, str):
        return compile(code, filename, 'exec')
    return code


@contextmanager
def relay_commands(q_commands: QueueCommands, command_queue_map: CommandQueueMap):
    '''Pass the Pdb commands from the main process to the Pdb instances.'''
    logger = getLogger(__name__)

    def fn() -> None:
        assert q_commands
        while m := q_commands.get():
            logger.debug(f'q_commands.get() -> {m!r}')
            command, prompt_no, trace_no = m
            command_queue_map[trace_no].put(m)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(try_again_on_error, fn)  # type: ignore
        try:
            yield
        finally:
            q_commands.put(None)
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
