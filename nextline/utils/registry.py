import threading
import asyncio
from collections import defaultdict
import warnings
from typing import AsyncGenerator, DefaultDict, Hashable, Any

from .coro_runner import CoroutineRunner
from .loop import ToLoop
from .queuedist import QueueDist


class DQ:
    def __init__(self):
        self._queue = QueueDist()

    def get(self):
        return self._queue.get()

    async def subscribe(self) -> AsyncGenerator[Any, None]:
        # To be called in the same thread in which __init__() is called
        async for y in self._queue.subscribe():
            yield y

    def put(self, item):
        self._queue.put(item)

    async def close(self):
        # To be called in the same thread in which __init__() is called
        await self._queue.close()


class Registry:
    """Subscribable asynchronous thread-safe registers"""

    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self._runner = CoroutineRunner().run
        self._lock = threading.Condition()
        self._aws = []

        to_loop = ToLoop()
        self._map: DefaultDict[str, DQ] = defaultdict(lambda: to_loop(DQ))

    async def close(self):
        """End gracefully"""
        if self._aws:
            await asyncio.gather(*self._aws)
        while self._map:
            _, dq = self._map.popitem()
            await dq.close()

    def open_register(self, key: Hashable):
        """Create a register for an item"""
        _ = self._map[key]

    def open_register_list(self, key: Hashable):
        """Create a register for an item list"""
        _ = self._map[key]

    def close_register(self, key: Hashable):
        """

        Can be called from any threads
        """
        dq = self._map.pop(key, None)
        if dq is None:
            return
        if task := self._runner(dq.close()):
            self._aws.append(task)

    def register(self, key, item):
        """Replace the item in the register"""
        self._map[key].put(item)

    def register_list_item(self, key, item):
        """Add an item to the register"""
        with self._lock:
            dp = self._map[key]
            copy = (dp.get() or []).copy()
            copy.append(item)
            dp.put(copy)

    def deregister_list_item(self, key, item):
        """Remove the item from the register"""
        with self._lock:
            dp = self._map[key]
            copy = dp.get().copy()
            try:
                copy.remove(item)
            except ValueError:
                warnings.warn(f"item not found: {item}")
            dp.put(copy)

    def get(self, key, default=None):
        """The item for the key. The default if the key doesn't exist"""
        if dp := self._map.get(key):
            return dp.get()
        else:
            return default

    async def subscribe(self, key):
        """Asynchronous generator of items in the register

        This method needs to be called in the initial thread.
        """
        dq = self._map[key]
        async for y in dq.subscribe():
            yield y
