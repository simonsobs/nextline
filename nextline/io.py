from __future__ import annotations

import io
from threading import Thread
import datetime
from collections import defaultdict

from typing import (
    TYPE_CHECKING,
    Callable,
    DefaultDict,
    NamedTuple,
    TextIO,
    Any,
)


from .utils import SubscribableDict, current_task_or_thread
from .types import StdoutInfo

if TYPE_CHECKING:
    from asyncio import Task


class OutLineItem(NamedTuple):
    key: Task | Thread
    line: str
    timestamp: datetime.datetime


class IOSubscription:
    def __init__(self, registry: SubscribableDict):
        self._registry = registry

        self._run_no_map = registry["run_no_map"]  # type: ignore
        self._trace_no_map = registry["trace_no_map"]  # type: ignore

    def __call__(self, src: TextIO):
        ret = IOPeekWrite(src, create_callback(self._put))
        return ret

    def _put(self, item: OutLineItem):
        if not (run_no := self._run_no_map.get(item.key)):
            return
        if not (trace_no := self._trace_no_map.get(item.key)):
            return
        info = StdoutInfo(
            run_no=run_no,
            trace_no=trace_no,
            text=item.line,
            written_at=item.timestamp,
        )
        # print(info, file=sys.stderr)
        self._registry["stdout"] = info


def create_callback(
    callback: Callable[[OutLineItem], None]
) -> Callable[[str], None]:
    buffer: DefaultDict[Thread | Task, str] = defaultdict(str)

    def ret(s: str) -> None:
        key = current_task_or_thread()
        buffer[key] += s
        if s.endswith("\n"):
            line = buffer.pop(key)
            now = datetime.datetime.now()
            item = OutLineItem(key, line, now)
            callback(item)

    return ret


class IOPeekWrite(io.TextIOWrapper):
    """Hook sys.stdout.write() or sys.stderr.write()"""

    def __init__(self, src: TextIO, callback: Callable[[str], None]):
        self._src = src
        self._callback = callback

    def write(self, s: str) -> int:
        src: TextIO = super().__getattribute__("_src")
        callback: Callable[[str], None] = super().__getattribute__("_callback")
        ret = src.write(s)
        callback(s)
        return ret

    def __getattribute__(self, name: str) -> Any:
        if name == "close":
            # not returning self._src.close so to avoid an error in pytest
            return super().__getattribute__(name)
        if name == "write":
            return super().__getattribute__(name)
        src = super().__getattribute__("_src")
        return getattr(src, name)
