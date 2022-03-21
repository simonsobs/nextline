import threading
import queue
import janus

from typing import AsyncGenerator, Generic, Type, Union, List, Tuple, TypeVar


class _Start:
    pass


class _End:
    pass


# TODO: Correct type hint. The type of yielded values in subscribe() is
# _QueueItem. It should be _T.

_T = TypeVar("_T")
_M = TypeVar("_M", Type[_Start], Type[_End])

_QueueItem = Union[_T, _M]
_Enumerated = Tuple[int, _QueueItem]


class QueueDist(Generic[_T]):
    """Distribute data to subscribers

    Data can be sent from any thread. Asynchronous subscriptions don't need to
    be all in the same thread.

    A new subscriber immediately receives the most recent issue of the past
    data and then wait for future issues.

    The order of the data is preserved.
    """

    def __init__(self):
        self._q_in: queue.Queue[_QueueItem] = queue.Queue()

        self._qs_out: List[janus.Queue[_Enumerated]] = []
        self._lock_out = threading.Condition()
        self._last_enumerated: _Enumerated = (-1, _Start)

        self._last_item: _T = None

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
        self._last_item = item
        self._q_in.put(item)

    def get(self) -> _T:
        """Most recent data that have been put"""
        return self._last_item

    async def subscribe(self) -> AsyncGenerator[_T, None]:
        """Yield data as they are put"""
        q: janus.Queue[_Enumerated] = janus.Queue()

        with self._lock_out:
            self._qs_out.append(q)

        last_idx, last_item = self._last_enumerated

        if last_item is _End:
            return

        try:
            if last_item is not _Start:
                yield last_item

            while True:
                idx, item = await q.async_q.get()
                if item is _End:
                    break
                if last_idx < idx:
                    yield item

        finally:
            with self._lock_out:
                self._qs_out.remove(q)

            q.close()
            await q.wait_closed()

    def close(self) -> None:
        """End gracefully"""
        with self._lock_close:
            if self._closed:
                return
            self._closed = True
            self._q_in.put(_End)
            self._thread.join()
            self._q_in.join()

    def _listen(self) -> None:
        """Distribution of data to subscribers

        This method runs in a thread.
        """
        idx, item = self._last_enumerated
        while item is not _End:
            idx += 1
            item = self._q_in.get()
            self._q_in.task_done()
            self._last_enumerated = (idx, item)
            with self._lock_out:
                for q in self._qs_out:
                    q.sync_q.put(self._last_enumerated)
