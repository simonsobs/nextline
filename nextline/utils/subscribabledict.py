from collections.abc import MutableMapping
from collections import defaultdict
from typing import AsyncGenerator, Optional, TypeVar, DefaultDict, Iterator

from .queuedist import QueueDist

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class SubscribableDict(MutableMapping):
    """Dict with async generator that yields changes"""

    def __init__(self):
        self._map: DefaultDict[_KT, QueueDist] = defaultdict(QueueDist)

    def __getitem__(self, key: _KT) -> _VT:
        if dp := self._map.get(key):
            return dp.get()
        else:
            raise KeyError

    def __setitem__(self, key: _KT, value: _VT) -> None:
        self._map[key].put(value)

    def __delitem__(self, key: _KT) -> None:
        dq = self._map.pop(key, None)
        if dq is None:
            return
        dq.close()

    def __iter__(self) -> Iterator[_KT]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def close(self):
        """End gracefully"""
        for key in list(self):
            del self[key]

    def get(self, key: _KT, default: Optional[_VT] = None) -> Optional[_VT]:
        """The item for the key. The default if the key doesn't exist"""
        if dp := self._map.get(key):
            return dp.get()
        else:
            return default

    async def subscribe(self, key: _KT) -> AsyncGenerator[_VT, None]:
        dq = self._map[key]
        async for y in dq.subscribe():  # type: ignore
            yield y
