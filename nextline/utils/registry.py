import threading
from collections import defaultdict
import warnings
from typing import DefaultDict

from .queuedist import QueueDist


class Registry:
    """Subscribable asynchronous thread-safe registers"""

    def __init__(self):
        self._lock = threading.Condition()

        self._map: DefaultDict[str, QueueDist] = defaultdict(QueueDist)

    def close(self):
        """End gracefully"""
        while self._map:
            _, dq = self._map.popitem()
            dq.close()

    def open_register(self, key):
        """Create a register for an item"""
        _ = self._map[key]

    def open_register_list(self, key):
        """Create a register for an item list"""
        _ = self._map[key]

    def close_register(self, key):
        """

        Can be called from any threads
        """
        dq = self._map.pop(key, None)
        if dq is None:
            return
        dq.close()

    def register(self, key, item):
        """Replace the item in the register"""
        self._map[key].put(item)

    def register_list_item(self, key, item):
        """Add an item to the register"""
        with self._lock:
            dp = self._map[key]
            copy = (dp.get() or ()) + (item,)
            dp.put(copy)

    def deregister_list_item(self, key, item):
        """Remove the item from the register"""
        with self._lock:
            dp = self._map[key]
            copy = list(dp.get())
            try:
                copy.remove(item)
            except ValueError:
                warnings.warn(f"item not found: {item}")
            copy = tuple(copy)
            dp.put(copy)

    def get(self, key, default=None):
        """The item for the key. The default if the key doesn't exist"""
        if dp := self._map.get(key):
            return dp.get()
        else:
            return default

    async def subscribe(self, key):
        dq = self._map[key]
        async for y in dq.subscribe():
            yield y
