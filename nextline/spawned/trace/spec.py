from __future__ import annotations

from asyncio import Task
from threading import Thread
from types import FrameType
from typing import TYPE_CHECKING, Collection, Generator, Optional

import apluggy as pluggy
from apluggy import PluginManager, contextmanager

from nextline.spawned.types import CommandQueueMap, QueueOut
from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceNo

from .types import TraceArgs

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.spawned.trace.plugins.registrar import RegistrarProxy

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
    queue_out: QueueOut,
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


@hookspec
def filtered(trace_args: TraceArgs) -> None:
    pass


@hookspec(firstresult=True)
def local_trace_func(frame: FrameType, event, arg) -> Optional[TraceFunc]:
    pass


@hookspec(firstresult=True)
def create_local_trace_func() -> Optional[TraceFunc]:
    pass


@hookspec
def on_start_task_or_thread() -> None:
    pass


@hookspec
def task_or_thread_end(task_or_thread: Task | Thread):
    pass


@hookspec
def on_start_trace(trace_no: TraceNo) -> None:
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
def on_end_trace(trace_no: TraceNo) -> None:
    pass


@hookspec
@contextmanager
def trace_call(trace_args: TraceArgs):
    pass


@hookspec(firstresult=True)
def is_on_trace_call() -> Optional[bool]:
    pass


@hookspec(firstresult=True)
def current_trace_args() -> Optional[TraceArgs]:
    pass


@hookspec
@contextmanager
def cmdloop():
    pass


@hookspec
@contextmanager
def on_prompt(prompt_no: PromptNo, text: str) -> Generator[None, str, None]:
    # Receive the command by gen.send().
    command = yield  # noqa: F841
    yield


@hookspec(firstresult=True)
def prompt(prompt_no: PromptNo, text: str) -> Optional[str]:
    pass


@hookspec
def stdout(trace_no: TraceNo, line: str) -> None:
    pass


@hookspec
def start() -> None:
    pass


@hookspec
def close(exc_type=None, exc_value=None, traceback=None) -> None:
    pass
