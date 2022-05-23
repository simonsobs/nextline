from __future__ import annotations

import io
import datetime
from collections import defaultdict

from typing import TYPE_CHECKING, DefaultDict, TextIO


from .utils import SubscribableQueue, current_task_or_thread
from .types import StdoutInfo

if TYPE_CHECKING:
    from asyncio import Task
    from threading import Thread
    from .utils import SubscribableDict


class IOSubscription(io.TextIOWrapper):
    def __init__(self, src: TextIO, registry: SubscribableDict):
        """Make output stream subscribable

        The src needs to be replaced with the instance of this class. For
        example, if the src is stdout,
            sys.stdout = IOSubscription(sys.stdout)

        NOTE: The code on the logic about the buffer copied from
        https://github.com/alphatwirl/atpbar/blob/894a7e0b4d81aa7b/atpbar/stream.py#L54
        """
        self.registry = registry
        self._queue = SubscribableQueue[StdoutInfo]()
        self._src = src
        self._buffer: DefaultDict[Task | Thread, str] = defaultdict(str)

        self._id_composer = registry["trace_id_factory"]  # type: ignore
        self._run_no_map = registry["run_no_map"]  # type: ignore
        self._trace_no_map = registry["trace_no_map"]  # type: ignore

    def write(self, s: str) -> int:

        ret = self._src.write(s)
        # TypeError if s isn't str as long as self._src is sys.stdout or
        # sys.stderr.

        if not self._id_composer.has_id():
            return ret

        key = current_task_or_thread()

        self._buffer[key] += s
        if s.endswith("\n"):
            self._put(key)
        return ret

    def _put(self, key):
        if not self._buffer[key]:
            return
        if not (run_no := self._run_no_map.get(key)):
            return
        if not (trace_no := self._trace_no_map.get(key)):
            return
        now = datetime.datetime.now()
        info = StdoutInfo(
            run_no=run_no,
            trace_no=trace_no,
            text=self._buffer[key],
            written_at=now,
        )
        # print(info, file=sys.stderr)
        self._queue.put(info)
        del self._buffer[key]

    def close(self):
        self._queue.close()

    def subscribe(self):
        return self._queue.subscribe(last=False)
