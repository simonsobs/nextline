import threading
import asyncio
import janus

##__________________________________________________________________||
class QueueDist:
    """
    """

    class End:
        pass

    class NoLastItem:
        pass

    def __init__(self):
        self._in = janus.Queue()

        self.condition = threading.Condition()
        self.subscribers = []
        self._last_item = self.NoLastItem

        self.t = threading.Thread(target=self._listen, daemon=True)
        self.t.start()

        self.condition = threading.Condition()

    def _listen(self):
        while True:
            m = self._in.sync_q.get()
            with self.condition:
                for q in self.subscribers:
                    q.sync_q.put(m)
                if m is self.End:
                    break
                self._last_item = m

    def put(self, item):
        self._in.sync_q.put(item)

    async def subscribe(self):
        q = janus.Queue()
        with self.condition:
            self.subscribers.append(q)
            if self._last_item is not self.NoLastItem:
                yield self._last_item
        while True:
            v = await q.async_q.get()
            if v is self.End:
                break
            yield v

    async def close(self):
        self._in.sync_q.put(self.End)

        try:
            await asyncio.to_thread(self.t.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.t.join)

        self._in.close()
        await self._in.wait_closed()

        for q in self.subscribers:
            q.close()
            await q.wait_closed()

##__________________________________________________________________||
