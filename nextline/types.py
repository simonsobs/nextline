from __future__ import annotations
import dataclasses
import datetime
from typing import Optional, Union


ThreadNo = int
TaskNo = Union[int, None]


@dataclasses.dataclass(frozen=True)
class ThreadTaskId:
    thread_no: ThreadNo
    task_no: TaskNo


@dataclasses.dataclass(frozen=True)
class RunInfo:
    run_no: int
    state: str
    script: Optional[str] = None
    result: Optional[str] = None
    exception: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None


@dataclasses.dataclass(frozen=True)
class TraceInfo:
    run_no: int
    state: str
    trace_no: int
    thread_no: int
    task_no: Optional[int] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None


@dataclasses.dataclass(frozen=True)
class PromptInfo:
    run_no: int
    trace_no: int
    prompt_no: int
    open: bool
    event: Optional[str] = None
    file_name: Optional[str] = None
    line_no: Optional[int] = None
    stdout: Optional[str] = None
    command: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None


@dataclasses.dataclass(frozen=True)
class StdoutInfo:
    run_no: int
    trace_no: int
    text: Optional[str] = None
    written_at: Optional[datetime.datetime] = None
