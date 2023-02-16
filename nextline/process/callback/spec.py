from typing import Optional

import pluggy

from nextline.types import PromptNo, TaskNo, ThreadNo, TraceNo

from .types import TraceArgs

PROJECT_NAME = 'nextline_process_callback'


hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookimpl
def trace_start(
    trace_no: TraceNo, thread_no: ThreadNo, task_no: Optional[TaskNo]
) -> None:
    pass


@hookspec
def trace_end(trace_no: TraceNo) -> None:
    pass


@hookspec
def trace_call_start(trace_no: TraceNo, trace_args: TraceArgs) -> None:
    pass


@hookspec
def trace_call_end(trace_no: TraceNo) -> None:
    pass


@hookspec
def prompt_start(
    trace_no: TraceNo, prompt_no: PromptNo, trace_args: TraceArgs, out: str
) -> None:
    pass


@hookspec
def prompt_end(trace_no: TraceNo, prompt_no: PromptNo, command: str) -> None:
    pass


@hookspec
def stdout(trace_no: TraceNo, line: str) -> None:
    pass
