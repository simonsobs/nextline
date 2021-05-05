import threading
import asyncio
import janus

##__________________________________________________________________||
class QueueDist:
    """Distribute queue inputs to subscribers
    """

    class End:
        pass

    class NoLastItem:
        pass

    def __init__(self):
        self.queue_in = janus.Queue()

        self.subscribers = []
        self.last_enumarated = (-1, self.NoLastItem)

        self.thread_listen = threading.Thread(target=self._listen, daemon=True)
        self.thread_listen.start()

    def _listen(self):
        idx = 0
        while True:
            item = self.queue_in.sync_q.get()
            enumarated = (idx, item)
            for q in self.subscribers:
                q.sync_q.put(enumarated)
            self.last_enumarated = enumarated
            if item is self.End:
                break
            idx += 1

    def put(self, item):
        self.queue_in.sync_q.put(item)

    async def subscribe(self):
        q = janus.Queue()
        self.subscribers.append(q)
        last_idx, last_item = self.last_enumarated
        if last_item is self.End:
            return
        if last_item is not self.NoLastItem:
            yield last_item
        while True:
            idx, item = await q.async_q.get()
            if item is self.End:
                break
            if last_idx < idx:
                yield item

    async def close(self):
        self.queue_in.sync_q.put(self.End)

        try:
            await asyncio.to_thread(self.thread_listen.join)
        except AttributeError:
            # for Python 3.8
            # to_thread() is new in Python 3.9
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.thread_listen.join)

        self.queue_in.close()
        await self.queue_in.wait_closed()

        for q in self.subscribers:
            q.close()
            await q.wait_closed()

##__________________________________________________________________||
