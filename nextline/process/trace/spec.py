from __future__ import annotations

from asyncio import Task
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Collection, Generator, Optional

import apluggy as pluggy
from apluggy import PluginManager, contextmanager

from nextline.process.types import CommandQueueMap
from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceNo

from .types import TraceArgs

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.trace.plugins.registrar import RegistrarProxy

PROJECT_NAME = 'nextline_process_callback'


hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def init(
    hook: PluginManager,
    run_no: RunNo,
    registrar: RegistrarProxy,
    command_queue_map: CommandQueueMap,
    modules_to_skip: Collection[str],
) -> None:
    pass


@hookspec(firstresult=True)
def global_trace_func(frame: FrameType, event, arg) -> Optional[TraceFunc]:
    pass


@hookspec(firstresult=True)
def filter(trace_args: TraceArgs) -> bool | None:
    '''True to reject, False to accept, None to pass to the next hook implementation.

    Accepted if no hook implementation returns True or False.
    '''
    pass


@hookspec(firstresult=True)
def local_trace_func(frame: FrameType, event, arg) -> Optional[TraceFunc]:
    pass


@hookspec
def task_or_thread_start() -> None:
    pass


@hookspec
def task_or_thread_end(task_or_thread: Task | Thread):
    pass


@hookspec
def trace_start(trace_no: TraceNo) -> None:
    pass


@hookspec(firstresult=True)
def current_thread_no() -> ThreadNo | None:
    pass


@hookspec(firstresult=True)
def current_task_no() -> TaskNo | None:
    pass


@hookspec(firstresult=True)
def current_trace_no() -> TraceNo | None:
    pass


@hookspec
def trace_end(trace_no: TraceNo) -> None:
    pass


@hookspec
@contextmanager
def trace_call(trace_no: TraceNo, trace_args: TraceArgs):
    pass


@hookspec
@contextmanager
def cmdloop(trace_no: TraceNo, trace_args: TraceArgs):
    pass


@hookspec
@contextmanager
def prompt(
    trace_no: TraceNo, prompt_no: PromptNo, trace_args: TraceArgs, out: str
) -> Generator[None, str, None]:
    # Receive the command by gen.send().
    command = yield  # noqa: F841
    yield


@hookspec
def stdout(trace_no: TraceNo, line: str) -> None:
    pass


@hookspec
def start() -> None:
    pass


@hookspec
def close(exc_type=None, exc_value=None, traceback=None) -> None:
    pass
