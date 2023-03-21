import dataclasses
import datetime
from typing import NewType, Optional

RunNo = NewType("RunNo", int)
TraceNo = NewType("TraceNo", int)
ThreadNo = NewType("ThreadNo", int)
TaskNo = NewType("TaskNo", int)
PromptNo = NewType("PromptNo", int)


@dataclasses.dataclass(frozen=True)
class ThreadTaskId:
    thread_no: ThreadNo
    task_no: Optional[TaskNo]


@dataclasses.dataclass(frozen=True)
class RunInfo:
    run_no: RunNo
    state: str
    script: Optional[str] = None
    result: Optional[str] = None
    exception: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None


@dataclasses.dataclass(frozen=True)
class TraceInfo:
    run_no: RunNo
    state: str
    trace_no: TraceNo
    thread_no: ThreadNo
    task_no: Optional[TaskNo] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None


@dataclasses.dataclass(frozen=True)
class PromptInfo:
    run_no: RunNo
    trace_no: TraceNo
    prompt_no: PromptNo
    open: bool
    event: Optional[str] = None
    file_name: Optional[str] = None
    line_no: Optional[int] = None
    stdout: Optional[str] = None
    command: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None
    trace_call_end: Optional[bool] = False  # TODO: remove when possible


@dataclasses.dataclass(frozen=True)
class PromptNotice:
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    prompt_no: PromptNo
    prompt_text: str
    event: str
    file_name: str
    line_no: int


@dataclasses.dataclass(frozen=True)
class StdoutInfo:
    run_no: RunNo
    trace_no: TraceNo
    text: Optional[str] = None
    written_at: Optional[datetime.datetime] = None
