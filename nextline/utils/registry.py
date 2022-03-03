from collections.abc import MutableMapping
from collections import defaultdict
from typing import Any, DefaultDict, Iterator

from .queuedist import QueueDist


class Registry(MutableMapping):
    """Subscribable asynchronous thread-safe registers"""

    def __init__(self):
        self._map: DefaultDict[str, QueueDist] = defaultdict(QueueDist)

    def __getitem__(self, key) -> Any:
        if dp := self._map.get(key):
            return dp.get()
        else:
            raise KeyError

    def __setitem__(self, key, value) -> None:
        self._map[key].put(value)

    def __delitem__(self, key) -> None:
        dq = self._map.pop(key, None)
        if dq is None:
            return
        dq.close()

    def __iter__(self) -> Iterator[Any]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def close(self):
        """End gracefully"""
        while self._map:
            _, dq = self._map.popitem()
            dq.close()

    def open_register(self, key):
        """Create a register for an item"""
        _ = self._map[key]

    def close_register(self, key):
        """

        Can be called from any threads
        """
        del self[key]

    def register(self, key, item):
        """Replace the item in the register"""
        self[key] = item

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
