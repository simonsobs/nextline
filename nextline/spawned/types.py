import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from types import CodeType, FrameType
from typing import Any, Callable, Optional, Tuple, Union

from typing_extensions import TypeAlias

from nextline.types import RunNo

from .commands import Command
from .events import Event

# if TYPE_CHECKING:
#     from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

# NOTE: TraceFunction from sys does not work well.
TraceFunction: TypeAlias = Callable[[FrameType, str, Any], "TraceFunction | None"]

TraceArgs: TypeAlias = Tuple[FrameType, str, Any]

QueueIn: TypeAlias = 'Queue[Command]'
QueueOut: TypeAlias = 'Queue[Event]'

Statement: TypeAlias = Union[str, Path, CodeType, Callable[[], Any]]


@dataclass
class RunArg:
    run_no: RunNo
    statement: Statement
    filename: Optional[str] = None


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
