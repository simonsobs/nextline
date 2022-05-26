from __future__ import annotations

import io
from queue import Queue
from threading import Thread
import datetime
from collections import defaultdict

from typing import (
    TYPE_CHECKING,
    Callable,
    DefaultDict,
    Mapping,
    NamedTuple,
    TextIO,
    Any,
)


from .utils import SubscribableQueue, current_task_or_thread
from .types import StdoutInfo

if TYPE_CHECKING:
    from asyncio import Task


class IOQueueItem(NamedTuple):
    key: Thread | Task
    text: str
    timestamp: datetime.datetime


class IOSubscription(io.TextIOWrapper):
    def __init__(self, src: TextIO, registry: Mapping):
        """Make output stream subscribable

        The src needs to be replaced with the instance of this class. For
        example, if the src is stdout,
            sys.stdout = IOSubscription(sys.stdout)

        """
        self._queue = SubscribableQueue[StdoutInfo]()

        self._run_no_map = registry["run_no_map"]  # type: ignore
        self._trace_no_map = registry["trace_no_map"]  # type: ignore

        self._q: Queue[IOQueueItem] = Queue()
        self._thread = Thread(target=self._listen, daemon=True)
        self._thread.start()

        self._s = IOPeekWrite(src, create_callback(self._q))

    def write(self, s: str) -> int:
        return self._s.write(s)

    def _listen(self) -> None:
        while m := self._q.get():
            self._put(*m)
            self._q.task_done()
        self._q.task_done()

    def _put(self, key, text, timestamp):
        if not (run_no := self._run_no_map.get(key)):
            return
        if not (trace_no := self._trace_no_map.get(key)):
            return
        info = StdoutInfo(
            run_no=run_no,
            trace_no=trace_no,
            text=text,
            written_at=timestamp,
        )
        # print(info, file=sys.stderr)
        self._queue.put(info)

    def close(self):
        self._q.put(None)
        self._q.join()
        self._thread.join()
        self._queue.close()

    def subscribe(self):
        return self._queue.subscribe(last=False)


def create_callback(queue: Queue[IOQueueItem]) -> Callable[[str], None]:
    buffer: DefaultDict[Thread | Task, str] = defaultdict(str)

    def callback(s: str) -> None:
        key = current_task_or_thread()
        buffer[key] += s
        if s.endswith("\n"):
            text = buffer.pop(key)
            now = datetime.datetime.now()
            item = IOQueueItem(key, text, now)
            queue.put(item)

    return callback


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
