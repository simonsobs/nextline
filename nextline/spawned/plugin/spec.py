from asyncio import Task
from collections.abc import Callable, Collection, Generator, Iterator
from threading import Thread
from types import FrameType
from typing import Any, Optional

import apluggy

from nextline.spawned.types import (
    QueueIn,
    QueueOut,
    RunArg,
    TraceArgs,
    TraceCallInfo,
    TraceFunction,
)
from nextline.types import PromptNo, TaskNo, ThreadNo, TraceNo

PROJECT_NAME = 'nextline_spawned'


hookspec = apluggy.HookspecMarker(PROJECT_NAME)
hookimpl = apluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def init(
    hook: apluggy.PluginManager,
    run_arg: RunArg,
    modules_to_skip: Collection[str],
    queue_in: QueueIn,
    queue_out: QueueOut,
) -> None:
    pass


@hookspec
@apluggy.contextmanager
def context():  # type: ignore
    pass


@hookspec(firstresult=True)
def compose_callable() -> Optional[Callable[[], Any]]:
    pass


@hookspec(firstresult=True)
def create_trace_func() -> Optional[TraceFunction]:
    pass


@hookspec
def clean_exception(exc: BaseException) -> None:
    pass


@hookspec(firstresult=True)
def global_trace_func(
    frame: FrameType, event: str, arg: Any
) -> Optional[TraceFunction]:
    pass


@hookspec(firstresult=True)
def filter(trace_args: TraceArgs) -> Optional[bool]:
    '''True to reject, False to accept, None to pass to the next hook implementation.

    Accepted if no hook implementation returns True or False.
    '''
    pass


@hookspec
def filtered(trace_args: TraceArgs) -> None:
    pass


@hookspec(firstresult=True)
def local_trace_func(frame: FrameType, event: str, arg: Any) -> Optional[TraceFunction]:
    pass


@hookspec(firstresult=True)
def create_local_trace_func() -> Optional[TraceFunction]:
    pass


@hookspec
def on_start_task_or_thread() -> None:
    pass


@hookspec
def on_end_task_or_thread(task_or_thread: Task | Thread) -> None:
    pass


@hookspec
def on_start_trace(trace_no: TraceNo) -> None:
    pass


@hookspec(firstresult=True)
def current_thread_no() -> Optional[ThreadNo]:
    pass


@hookspec(firstresult=True)
def current_task_no() -> Optional[TaskNo]:
    pass


@hookspec(firstresult=True)
def current_trace_no() -> Optional[TraceNo]:
    pass


@hookspec
def on_end_trace(trace_no: TraceNo) -> None:
    pass


@hookspec
@apluggy.contextmanager
def on_trace_call(trace_call_info: TraceCallInfo) -> Iterator[None]:
    yield


@hookspec(firstresult=True)
def is_on_trace_call() -> Optional[bool]:
    pass


@hookspec(firstresult=True)
def current_trace_args() -> Optional[TraceArgs]:
    pass


@hookspec(firstresult=True)
def current_trace_call_info() -> Optional[TraceCallInfo]:
    pass


@hookspec
@apluggy.contextmanager
def on_cmdloop():  # type: ignore
    pass


@hookspec
@apluggy.contextmanager
def on_prompt(prompt_no: PromptNo, text: str) -> Generator[None, str, None]:
    # Receive the command by gen.send().
    command = yield  # noqa: F841
    yield


@hookspec(firstresult=True)
def prompt(prompt_no: PromptNo, text: str) -> Optional[str]:
    pass


@hookspec
def on_write_stdout(trace_no: TraceNo, line: str) -> None:
    pass
