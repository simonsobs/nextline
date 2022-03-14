from collections.abc import MutableMapping
from collections import defaultdict
from typing import AsyncGenerator, Optional, TypeVar, DefaultDict, Iterator

from .queuedist import QueueDist

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class SubscribableDict(MutableMapping):
    """Dict with async generator that yields values as they change"""

    def __init__(self):
        self._map: DefaultDict[_KT, QueueDist] = defaultdict(QueueDist)

    def subscribe(self, key: _KT) -> AsyncGenerator[_VT, None]:
        """Async generator that yields values for the key as they are set

        Yields immediately the current value for the key, wait for new values
        and yield them as they are set. Wait for the first value for the key if
        the key doesn't exist; KeyError won't be raised.
        """
        return self._map[key].subscribe()

    def __getitem__(self, key: _KT) -> _VT:
        """The current value for the key. KeyError if the key doesn't exist."""
        if q := self._map.get(key):
            return q.get()
        else:
            raise KeyError

    def get(self, key: _KT, default: Optional[_VT] = None) -> Optional[_VT]:
        """The current value for the key if the key exist, else the default"""
        if q := self._map.get(key):
            return q.get()
        else:
            return default

    def __setitem__(self, key: _KT, value: _VT) -> None:
        """Set the value for the key, yielding the value in the generators"""
        self._map[key].put(value)

    def __delitem__(self, key: _KT) -> None:
        """Remove the key, ending all subscriptions for the key

        The async generators returned by the method `subscribe()` for the key
        will return.

        KeyError will be raised if the key doesn't exist
        """
        self._map.pop(key).close()

    def close(self):
        """Remove all keys, ending all subscriptions for all keys"""
        while True:
            try:
                self.popitem()  # __delitem__() will be called
            except KeyError:
                break

    def __iter__(self) -> Iterator[_KT]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)
