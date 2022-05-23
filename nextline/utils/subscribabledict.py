from __future__ import annotations
from collections import defaultdict
from typing import (
    overload,
    Generic,
    Optional,
    TypeVar,
    DefaultDict,
    Iterator,
    MutableMapping,
)

from .subscribablequeue import SubscribableQueue

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")


class SubscribableDict(MutableMapping[_KT, _VT], Generic[_KT, _VT]):
    """Dict with async generator that yields values as they change"""

    def __init__(self):
        self._map: DefaultDict[_KT, SubscribableQueue[_VT]] = defaultdict(SubscribableQueue)

    def subscribe(self, key: _KT, last: Optional[bool] = True):
        """Async generator that yields values for the key as they are set

        Waits for new values and yields them as they are set. If `last` is
        true, yields immediately the current value for the key before starting
        to wait. If the key doesn't exist, waits for the first value for the
        key; KeyError won't be raised.

        """
        return self._map[key].subscribe(last=last)

    def __getitem__(self, key: _KT) -> _VT:
        """The current value for the key. KeyError if the key doesn't exist."""
        if q := self._map.get(key):
            return q.get()
        else:
            raise KeyError

    @overload
    def get(self, key: _KT) -> Optional[_VT]:
        ...

    @overload
    def get(self, key: _KT, default: _VT | _T) -> _VT | _T:
        ...

    def get(self, key, default=None):
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

    def close(self) -> None:
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
