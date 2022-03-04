from collections.abc import MutableMapping
from collections import defaultdict
from typing import Any, DefaultDict, Iterator

from .queuedist import QueueDist


class SubscribableDict(MutableMapping):
    """Dict with async generator that yields changes
    """

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
        for key in list(self):
            del self[key]

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
