import threading
import asyncio
from dataclasses import dataclass
import warnings
from typing import Dict, Hashable, Coroutine, Any

from .coro_runner import CoroutineRunner
from .queuedist import QueueDist


@dataclass
class DQ:
    data: Any = None
    queue: QueueDist = None


##__________________________________________________________________||
class Registry:
    """Subscribable asynchronous thread-safe registers"""

    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self._runner = CoroutineRunner()
        self._lock = threading.Condition()
        # self._data = {}
        # self._queue = {}
        self._aws = []
        self._map: Dict[str, DQ] = {}

    async def close(self):
        """End gracefully"""
        if self._aws:
            await asyncio.gather(*self._aws)
        while self._map:
            _, dq = self._map.popitem()
            await dq.queue.close()
        # while self._queue:
        #     _, q = self._queue.popitem()
        # await q.close()
        # self._data.clear()

    def open_register(self, key: Hashable):
        """Create a register for an item"""
        self._open_register(key, None)

    def open_register_list(self, key: Hashable):
        """Create a register for an item list"""
        self._open_register(key, [])

    def _open_register(self, key, init_data):
        # if key in self._data:
        #     raise Exception(f"register key already exists {key!r}")
        # self._data[key] = init_data
        if key in self._map:
            self._map[key].data = init_data
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._loop is loop:
            self._create_queue(key, init_data)
        else:
            self._create_queue_from_another_thread(key, init_data)

    def close_register(self, key: Hashable):
        # try:
        #     del self._data[key]
        # except KeyError:
        #     warnings.warn(f"key not found: {key}")
        self._close_queue_from_another_thread(key)

    def register(self, key, item):
        """Replace the item in the register"""
        # if key not in self._data:
        #     raise Exception(f"register key does not exist {key!r}")

        # self._data[key] = item
        self._map[key].data = item

        self._distribute(key, item)

    def register_list_item(self, key, item):
        """Add an item to the register"""
        # if key not in self._data:
        #     raise Exception(f"register key does not exist {key!r}")

        with self._lock:
            # self._data[key].append(item)
            # copy = self._data[key].copy()
            self._map[key].data.append(item)
            copy = self._map[key].data.copy()

        self._distribute(key, copy)

    def deregister_list_item(self, key, item):
        """Remove the item from the register"""
        # if key not in self._data:
        #     raise Exception(f"register key does not exist {key!r}")

        with self._lock:
            try:
                # self._data[key].remove(item)
                self._map[key].data.remove(item)
            except ValueError:
                warnings.warn(f"item not found: {item}")
            # copy = self._data[key].copy()
            copy = self._map[key].data.copy()

        self._distribute(key, copy)

    def get(self, key, default=None):
        """The item for the key. The default if the key doesn't exist"""
        # return self._data.get(key, default)
        if dp := self._map.get(key):
            return dp.data
        else:
            return default

    async def subscribe(self, key):
        """Asynchronous generator of items in the register

        This method needs to be called in the initial thread.
        """
        # queue = self._queue.get(key)
        # if not queue:
        #     self._create_queue(key)
        #     queue = self._queue.get(key)
        # async for y in queue.subscribe():
        #     yield y
        dq = self._map.get(key)
        if not dq:
            self._create_queue(key)
            dq = self._map[key]
        async for y in dq.queue.subscribe():
            yield y

    def _create_queue_from_another_thread(self, key, init_data):
        """Open a queue

        Can be called from any threads
        """

        async def create():
            self._create_queue(key, init_data)

        self._run_in_the_initial_thread(create())

    def _create_queue(self, key, init_data=None):
        """Open a queue

        To be run in the initial thread
        """
        # if key in self._queue:
        #     return
        if key in self._map:
            return
        q = QueueDist()
        # self._queue[key] = q
        self._map[key] = DQ(data=init_data, queue=q)

    def _close_queue_from_another_thread(self, key):
        """Remove the queue

        Can be called from any threads
        """
        coro = self._close_queue(key)
        self._run_in_the_initial_thread(coro)

    async def _close_queue(self, key):
        """Remove the queue

        To be run in the initial thread
        """
        # queue = self._queue.pop(key, None)
        # if queue:
        #     await queue.close()
        dq = self._map.pop(key, None)
        if dq:
            await dq.queue.close()

    def _distribute(self, key, item):
        """Send item to subscribers"""

        async def put():
            # self._queue[key].put(item)
            self._map[key].queue.put(item)

        self._run_in_the_initial_thread(put())

    def _run_in_the_initial_thread(self, coro: Coroutine):
        """Schedule the coroutine as an asyncio task

        The task will be scheduled to the asyncio event loop in the thread in
        which this class is instantiated.
        """
        task = self._runner.run(coro)
        if task:
            self._aws.append(task)


##__________________________________________________________________||
