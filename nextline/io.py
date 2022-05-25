from __future__ import annotations

import io
from queue import Queue
from threading import Thread
import datetime
from collections import defaultdict

from typing import TYPE_CHECKING, Any, DefaultDict, Mapping, TextIO


from .utils import SubscribableQueue, current_task_or_thread
from .types import StdoutInfo

if TYPE_CHECKING:
    from asyncio import Task


def create_key_factory(to_put):
    def key_factory():
        if not to_put():
            return None
        return current_task_or_thread()

    return key_factory


class IOSubscription(io.TextIOWrapper):
    def __init__(self, src: TextIO, registry: Mapping):
        """Make output stream subscribable

        The src needs to be replaced with the instance of this class. For
        example, if the src is stdout,
            sys.stdout = IOSubscription(sys.stdout)

        """
        self.registry = registry
        self._queue = SubscribableQueue[StdoutInfo]()
        self._src = src
        self._buffer: DefaultDict[Task | Thread, str] = defaultdict(str)

        self._run_no_map = registry["run_no_map"]  # type: ignore
        self._trace_no_map = registry["trace_no_map"]  # type: ignore

        self._q: Queue[Any] = Queue()
        self._thread = Thread(target=self._listen, daemon=True)
        self._thread.start()

        id_composer = registry["trace_id_factory"]  # type: ignore
        self._key_factory = create_key_factory(to_put=id_composer.has_id)
        self._s = Scratch(
            src=src,
            queue=self._q,
            key_factory=self._key_factory,
        )

    def write(self, s: str) -> int:
        return self._s.write(s)

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

    def _listen(self) -> None:
        while m := self._q.get():
            self._put(*m)
            self._q.task_done()
        self._q.task_done()


class Scratch(io.TextIOWrapper):
    def __init__(self, src: TextIO, queue, key_factory):
        self._queue = queue
        self._src = src
        self._key_factory = key_factory
        self._buffer: DefaultDict[Any, str] = defaultdict(str)

    def write(self, s: str) -> int:

        ret = self._src.write(s)
        # TypeError if s isn't str as long as self._src is sys.stdout or
        # sys.stderr.

        if not (key := self._key_factory()):
            return ret

        self._buffer[key] += s
        if s.endswith("\n"):
            self._queue.put(
                (key, self._buffer.pop(key), datetime.datetime.now())
            )
        return ret
