from __future__ import annotations
from collections import defaultdict, UserDict
from typing import (
    AsyncIterator,
    Generic,
    Optional,
    TypeVar,
    DefaultDict,
    MutableMapping,
)

from .subscribablequeue import SubscribableQueue

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class SubscribableDict(UserDict, MutableMapping[_KT, _VT], Generic[_KT, _VT]):
    """Dict with async generator that yields values as they change"""

    def __init__(self, *args, **kwargs):
        self._queue: DefaultDict[_KT, SubscribableQueue[_VT]] = defaultdict(
            SubscribableQueue
        )
        super().__init__(*args, **kwargs)

    def subscribe(
        self, key: _KT, last: Optional[bool] = True
    ) -> AsyncIterator[_VT]:
        """Async generator that yields values for the key as they are set

        Waits for new values and yields them as they are set. If `last` is
        true, yields immediately the current value for the key before starting
        to wait. If the key doesn't exist, waits for the first value for the
        key; KeyError won't be raised.

        """
        return self._queue[key].subscribe(last=last)

    def __setitem__(self, key: _KT, value: _VT) -> None:
        """Set the value for the key, yielding the value in the generators"""
        super().__setitem__(key, value)
        self._queue[key].put(value)

    def __delitem__(self, key: _KT) -> None:
        """Remove the key, ending all subscriptions for the key

        The async generators returned by the method `subscribe()` for the key
        will return.

        KeyError will be raised if the key doesn't exist
        """
        super().__delitem__(key)
        self._queue.pop(key).close()

    def close(self) -> None:
        """Remove all keys, ending all subscriptions for all keys"""
        while True:
            try:
                self.popitem()  # __delitem__() will be called
            except KeyError:
                break
        while True:
            try:
                k, v = self._queue.popitem()
            except KeyError:
                break
            v.close()
