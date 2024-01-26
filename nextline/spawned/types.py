import json
import traceback
from dataclasses import dataclass, field
from queue import Queue
from types import FrameType
from typing import Any, Callable, Optional

from nextline.events import Event
from nextline.spawned.path import to_canonic_path
from nextline.types import RunNo, Statement

from .commands import Command

# if TYPE_CHECKING:
#     from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

# NOTE: TraceFunction from sys does not work well.
TraceFunction = Callable[[FrameType, str, Any], "TraceFunction | None"]

TraceArgs = tuple[FrameType, str, Any]

QueueIn = Queue[Command]
QueueOut = Queue[Event]


@dataclass
class RunArg:
    run_no: RunNo
    statement: Statement
    filename: Optional[str] = None
    trace_threads: bool = True
    trace_modules: bool = True


@dataclass
class RunResult:
    ret: Optional[Any] = None
    exc: Optional[BaseException] = None
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


@dataclass
class TraceCallInfo:
    args: TraceArgs
    file_name: str = field(init=False)
    line_no: int = field(init=False)
    frame_object_id: int = field(init=False)
    event: str = field(init=False)

    def __post_init__(self) -> None:
        frame, event, _ = self.args
        self.file_name = to_canonic_path(frame.f_code.co_filename)
        self.line_no = frame.f_lineno
        self.frame_object_id = id(frame)
        self.event = event
