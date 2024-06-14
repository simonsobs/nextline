import datetime
from dataclasses import dataclass
from typing import Optional

from nextline.types import (
    PromptNo,
    RunNo,
    Statement,
    TaskNo,
    ThreadNo,
    TraceCallNo,
    TraceNo,
)
from nextline.utils import is_timezone_aware


@dataclass
class Event:
    pass


@dataclass
class OnStartRun(Event):
    started_at: datetime.datetime
    run_no: RunNo
    statement: Statement

    def __post_init__(self):
        _assert_aware_datetime(self.started_at)


@dataclass
class OnEndRun(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    returned: str
    raised: str

    def __post_init__(self):
        _assert_aware_datetime(self.ended_at)


@dataclass
class OnStartTrace(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    thread_no: ThreadNo
    task_no: Optional[TaskNo]

    def __post_init__(self):
        _assert_naive_datetime(self.started_at)


@dataclass
class OnEndTrace(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo

    def __post_init__(self):
        _assert_naive_datetime(self.ended_at)


@dataclass
class OnStartTraceCall(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    trace_call_no: TraceCallNo
    file_name: str
    line_no: int
    frame_object_id: int
    event: str

    def __post_init__(self):
        _assert_naive_datetime(self.started_at)


@dataclass
class OnEndTraceCall(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    trace_call_no: TraceCallNo

    def __post_init__(self):
        _assert_naive_datetime(self.ended_at)


@dataclass
class OnStartCmdloop(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    trace_call_no: TraceCallNo

    def __post_init__(self):
        _assert_naive_datetime(self.started_at)


@dataclass
class OnEndCmdloop(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    trace_call_no: TraceCallNo

    def __post_init__(self):
        _assert_naive_datetime(self.ended_at)


@dataclass
class OnStartPrompt(Event):
    started_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    trace_call_no: TraceCallNo
    prompt_no: PromptNo
    prompt_text: str
    file_name: str
    line_no: int
    frame_object_id: int
    event: str

    def __post_init__(self):
        _assert_naive_datetime(self.started_at)


@dataclass
class OnEndPrompt(Event):
    ended_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    trace_call_no: TraceCallNo
    prompt_no: PromptNo
    command: str

    def __post_init__(self):
        _assert_naive_datetime(self.ended_at)


@dataclass
class OnWriteStdout(Event):
    written_at: datetime.datetime
    run_no: RunNo
    trace_no: TraceNo
    text: str

    def __post_init__(self):
        _assert_naive_datetime(self.written_at)


def _assert_naive_datetime(dt: datetime.datetime):
    if is_timezone_aware(dt):
        raise ValueError(f'Not a timezone-naive object: {dt!r}')


def _assert_aware_datetime(dt: datetime.datetime):
    if not is_timezone_aware(dt):
        raise ValueError(f'Not a timezone-aware object: {dt!r}')
