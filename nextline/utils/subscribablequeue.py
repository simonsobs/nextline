from __future__ import annotations

import enum
import threading
from queue import Queue
from janus import Queue as Janus, SyncQueue

from typing import (
    AsyncIterator,
    Generic,
    Literal,
    Optional,
    List,
    Tuple,
    TypeVar,
)


class _M(enum.Enum):
    # TODO: Using Enum as sentinel for now as suggested in
    # https://stackoverflow.com/a/60605919/7309855. It still has a problem. For
    # example, the type of yielded values in subscribe() is not correctly
    # inferred as _T.

    START = object()
    END = object()


_T = TypeVar("_T")


class SubscribableQueue(Generic[_T]):
    """Distribute items to subscribers

    Items can be sent from any threads. Asynchronous subscriptions don't need
    to be all in the same thread.

    A new subscriber immediately receives the latest item and then wait for new
    items.

    The order of the items is preserved.
    """

    def __init__(self):

        self._q_in: Queue[_T | Literal[_M.END]] = Queue()

        self._qs_out: List[
            Queue[Tuple[int, _T | Literal[_M.END]]]
            | SyncQueue[Tuple[int, _T | Literal[_M.END]]]
        ] = []
        self._last_enumerated: Tuple[
            int, _T | Literal[_M.START] | Literal[_M.END]
        ] = (-1, _M.START)

        self._last_item: _T | Literal[_M.START] = _M.START

        self._closed: bool = False
        self._lock_close = threading.Condition()

        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    @property
    def nsubscriptions(self) -> int:
        """The number of the subscribers"""
        return len(self._qs_out)

    def put(self, item: _T) -> None:
        """Send data to subscribers

        This method can be called in any thread.
        """
        if self._closed:
            raise RuntimeError(f"{self} is closed.")
        self._last_item = item
        self._q_in.put(item)

    def get(self) -> _T:
        """Most recent data that have been put"""
        if self._last_item is _M.START:
            raise LookupError
        return self._last_item

    async def subscribe(
        self,
        last: Optional[bool] = True,
    ) -> AsyncIterator[_T]:
        """Yield data as they are put

        If `last` is true, yield immediately the most recent data before
        waiting for new data.
        """
        q: Janus[Tuple[int, _T | Literal[_M.END]]] = Janus()

        self._qs_out.append(q.sync_q)

        last_idx, last_item = self._last_enumerated

        if last_item is _M.END:
            return

        try:
            if last and last_item is not _M.START:
                yield last_item

            while True:
                idx, item = await q.async_q.get()
                if item is _M.END:
                    break
                if last_idx < idx:
                    yield item

        finally:
            self._qs_out.remove(q.sync_q)

            q.close()
            await q.wait_closed()

    def close(self) -> None:
        """End gracefully"""
        with self._lock_close:
            if self._closed:
                return
            self._closed = True
            self._q_in.put(_M.END)
            self._thread.join()
            self._q_in.join()

    def _listen(self) -> None:
        """Distribution of data to subscribers

        This method runs in a thread.
        """
        idx, item = self._last_enumerated
        while item is not _M.END:
            idx += 1
            item = self._q_in.get()
            self._q_in.task_done()
            self._last_enumerated = (idx, item)
            for q in list(self._qs_out):  # list in case it changes in a thread
                q.put(self._last_enumerated)
