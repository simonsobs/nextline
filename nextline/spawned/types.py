import datetime
import json
import traceback
from dataclasses import dataclass, field
from queue import Queue
from typing import Any, MutableMapping, Optional, Tuple, TypedDict

from typing_extensions import TypeAlias

from nextline.types import PromptNo, RunNo, TaskNo, ThreadNo, TraceNo

PdbCommand: TypeAlias = str
QueueCommands: TypeAlias = "Queue[Tuple[PdbCommand, PromptNo, TraceNo] | None]"

CommandQueueMap: TypeAlias = MutableMapping[
    TraceNo, 'Queue[Tuple[PdbCommand, PromptNo, TraceNo]]'
]


@dataclass
class Event:
    pass


@dataclass
class OnStartTrace(Event):
    started_at: datetime.datetime
    trace_no: TraceNo
    thread_no: ThreadNo
    task_no: Optional[TaskNo]


@dataclass
class OnEndTrace(Event):
    ended_at: datetime.datetime
    trace_no: TraceNo


@dataclass
class OnStartTraceCall(Event):
    started_at: datetime.datetime
    trace_no: TraceNo
    file_name: str
    line_no: int
    frame_object_id: int
    call_event: str


@dataclass
class OnEndTraceCall(Event):
    ended_at: datetime.datetime
    trace_no: TraceNo


@dataclass
class OnStartCmdloop(Event):
    started_at: datetime.datetime
    trace_no: TraceNo


@dataclass
class OnEndCmdloop(Event):
    ended_at: datetime.datetime
    trace_no: TraceNo


@dataclass
class OnStartPrompt(Event):
    started_at: datetime.datetime
    trace_no: TraceNo
    prompt_no: PromptNo
    prompt_text: str


@dataclass
class OnEndPrompt(Event):
    ended_at: datetime.datetime
    trace_no: TraceNo
    prompt_no: PromptNo
    command: str


@dataclass
class OnWriteStdout(Event):
    written_at: datetime.datetime
    trace_no: TraceNo
    text: str


QueueOut: TypeAlias = 'Queue[Event]'


class RunArg(TypedDict):
    run_no: RunNo
    statement: str
    filename: str


@dataclass
class RunResult:
    ret: Optional[Any]
    exc: Optional[BaseException]
    _fmt_ret: Optional[str] = field(init=False, repr=False, default=None)
    _fmt_exc: Optional[str] = field(init=False, repr=False, default=None)

    @property
    def fmt_ret(self) -> str:
        if self._fmt_ret is None:
            self._fmt_ret = json.dumps(self.ret)
        return self._fmt_ret

    @property
    def fmt_exc(self) -> str:
        if self._fmt_exc is None:
            if self.exc is None:
                self._fmt_exc = ''
            else:
                self._fmt_exc = ''.join(
                    traceback.format_exception(
                        type(self.exc),
                        self.exc,
                        self.exc.__traceback__,
                    )
                )
        return self._fmt_exc

    def result(self) -> Any:
        if self.exc is not None:
            # TODO: add a test for the exception
            raise self.exc
        return self.ret
