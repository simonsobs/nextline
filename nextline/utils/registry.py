import threading
import asyncio
import warnings
from typing import AsyncGenerator, Dict, Hashable, Any

from .coro_runner import CoroutineRunner
from .loop import ToLoop
from .queuedist import QueueDist


class DQ:
    def __init__(self, data: Any = None):
        self._data = data
        self._queue = QueueDist()

    async def subscribe(self) -> AsyncGenerator[Any, None]:
        async for y in self._queue.subscribe():
            yield y

    def put(self, item):
        self._queue.put(item)

    async def close(self):
        await self._queue.close()

    @property
    def value(self):
        return self._data

class Registry:
    """Subscribable asynchronous thread-safe registers"""

    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self._runner = CoroutineRunner().run
        self._to_loop = ToLoop()
        self._lock = threading.Condition()
        self._aws = []
        self._map: Dict[str, DQ] = {}

    async def close(self):
        """End gracefully"""
        if self._aws:
            await asyncio.gather(*self._aws)
        while self._map:
            _, dq = self._map.popitem()
            await dq.close()

    def open_register(self, key: Hashable):
        """Create a register for an item"""
        self._open_register(key, None)

    def open_register_list(self, key: Hashable):
        """Create a register for an item list"""
        self._open_register(key, [])

    def _open_register(self, key, init_data):
        if dq := self._map.get(key):
            dq._data = init_data
            return
        dq = self._to_loop(DQ, data=init_data)
        self._map[key] = dq

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
        self._map[key]._data = item
        self._to_loop(self._map[key].put, item)

    def register_list_item(self, key, item):
        """Add an item to the register"""
        with self._lock:
            copy = self._map[key].value.copy()
            copy.append(item)
            self._map[key]._data = copy
        self._to_loop(self._map[key].put, copy)

    def deregister_list_item(self, key, item):
        """Remove the item from the register"""
        with self._lock:
            copy = self._map[key].value.copy()
            try:
                copy.remove(item)
            except ValueError:
                warnings.warn(f"item not found: {item}")
            self._map[key]._data = copy

        self._to_loop(self._map[key].put, copy)

    def get(self, key, default=None):
        """The item for the key. The default if the key doesn't exist"""
        if dp := self._map.get(key):
            return dp.value
        else:
            return default

    async def subscribe(self, key):
        """Asynchronous generator of items in the register

        This method needs to be called in the initial thread.
        """
        dq = self._map.get(key)
        if not dq:
            dq = DQ()
            self._map[key] = dq
        async for y in dq.subscribe():
            yield y
