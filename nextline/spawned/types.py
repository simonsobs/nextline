import json
import traceback
from dataclasses import dataclass, field
from queue import Queue
from types import FrameType
from typing import Any, Callable, Optional

from nextline.types import RunNo, Statement

from .commands import Command
from .events import Event

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
