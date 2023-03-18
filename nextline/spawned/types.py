import json
import traceback
from dataclasses import dataclass, field
from queue import Queue
from typing import Any, MutableMapping, Optional, Tuple, TypedDict

from typing_extensions import TypeAlias

from nextline.types import PromptNo, RunNo, TraceNo

from .commands import Command
from .events import Event

QueueCommands: TypeAlias = "Queue[Tuple[str, PromptNo, TraceNo] | None]"

CommandQueueMap: TypeAlias = MutableMapping[
    TraceNo, 'Queue[Tuple[str, PromptNo, TraceNo]]'
]


QueueIn: TypeAlias = 'Queue[Command]'
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
