import threading
import queue
import janus

from typing import Any, AsyncIterable, List, Tuple


class QueueDist:
    """Distribute data to subscribers

    Data can be sent from any thread. Asynchronous subscriptions don't need to
    be all in the same thread.

    A new subscriber immediately receives the most recent issue of the past
    data and then wait for future issues.

    The order of the data is preserved.
    """

    class End:
        pass

    class Start:
        pass

    def __init__(self):
        self._q_in = queue.Queue()

        self._qs_out: List[janus.Queue] = []
        self._lock_out = threading.Condition()
        self._last_enumerated: Tuple[int, Any] = (-1, self.Start)

        self._last_item: Any = None

        self._closed: bool = False
        self._lock_close = threading.Condition()

        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    @property
    def nsubscriptions(self) -> int:
        """The number of the subscribers"""
        return len(self._qs_out)

    def put(self, item: Any) -> None:
        """Send data to subscribers

        This method can be called in any thread.
        """
        self._last_item = item
        self._q_in.put(item)

    def get(self) -> Any:
        """Most recent data that have been put"""
        return self._last_item

    async def subscribe(self) -> AsyncIterable:
        """Yield data as they are put"""
        q: janus.Queue = janus.Queue()

        with self._lock_out:
            self._qs_out.append(q)

        last_idx, last_item = self._last_enumerated

        if last_item is self.End:
            return

        try:
            if last_item is not self.Start:
                yield last_item

            while True:
                idx, item = await q.async_q.get()
                if item is self.End:
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
            self._q_in.put(self.End)
            self._thread.join()
            self._q_in.join()

    def _listen(self) -> None:
        """Distribution of data to subscribers

        This method runs in a thread.
        """
        idx, item = self._last_enumerated
        while item is not self.End:
            idx += 1
            item = self._q_in.get()
            self._q_in.task_done()
            self._last_enumerated = (idx, item)
            with self._lock_out:
                for q in self._qs_out:
                    q.sync_q.put(self._last_enumerated)
