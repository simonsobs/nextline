import datetime
from dataclasses import dataclass
from typing import Optional

from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceNo


@dataclass
class Event:
    pass


@dataclass
class OnStartTrace(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    thread_no: ThreadNo
    task_no: Optional[TaskNo]


@dataclass
class OnEndTrace(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo


@dataclass
class OnStartTraceCall(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    file_name: str
    line_no: int
    frame_object_id: int
    event: str


@dataclass
class OnEndTraceCall(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo


@dataclass
class OnStartCmdloop(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo


@dataclass
class OnEndCmdloop(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo


@dataclass
class OnStartPrompt(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    prompt_no: PromptNo
    prompt_text: str
    file_name: str
    line_no: int
    frame_object_id: int
    event: str


@dataclass
class OnEndPrompt(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    prompt_no: PromptNo
    command: str


@dataclass
class OnWriteStdout(Event):
    written_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    text: str
