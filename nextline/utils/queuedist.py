import threading
import asyncio
import janus


##__________________________________________________________________||
class QueueDist:
    """Distribute data to subscribers

    Data can be sent from any thread. All subscribers need to be in the thread
    in which this class is instantiated.

    A new subscriber immediatly receives the most recent issue of the past data
    and then wait for future issues.

    The order of the data is preserved.
    """

    class End:
        pass

    class Start:
        pass

    def __init__(self):
        self._q_in = janus.Queue()

        self._qs_out = []  # list of janus.Queue()
        self._lock_out = threading.Condition()
        self._last_enumarated = (-1, self.Start)

        self._closed = False
        self._lock_close = asyncio.Condition()

        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    @property
    def nsubscriptions(self):
        """The number of the subscribers"""
        return len(self._qs_out)

    def put(self, item):
        """Send data to subscribers

        This method can be called in any thread.
        """
        self._q_in.sync_q.put(item)

    async def subscribe(self):
        """Asynchronous generator of data

        This method needs to be called in the thread in which this class
        is instantiated.
        """
        q = janus.Queue()

        with self._lock_out:
            self._qs_out.append(q)

        last_idx, last_item = self._last_enumarated

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

    async def close(self):
        """End gracefully

        This method needs to be called in the thread in which this class
        is instantiated.
        """
        async with self._lock_close:
            if self._closed:
                return
            await self._close()
            self._closed = True

    async def _close(self):
        """Actual implementation of close()"""
        self._q_in.sync_q.put(self.End)

        try:
            await asyncio.to_thread(self._thread.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._thread.join)

        self._q_in.close()
        await self._q_in.wait_closed()

    def _listen(self):
        """Distribution of data to subscribers

        This method runs in a thread.
        """
        idx, item = self._last_enumarated
        while item is not self.End:
            idx += 1
            item = self._q_in.sync_q.get()
            enumarated = (idx, item)
            with self._lock_out:
                for q in self._qs_out:
                    q.sync_q.put(enumarated)
            self._last_enumarated = enumarated


##__________________________________________________________________||
