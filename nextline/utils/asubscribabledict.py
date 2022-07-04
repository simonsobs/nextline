from __future__ import annotations
from typing import AsyncIterator, Generic, Optional, TypeVar

from .asubscribablequeue import ASubscribableQueue
from ._userdict import UserDict

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class QueueDict(UserDict[_KT, ASubscribableQueue[_VT]], Generic[_KT, _VT]):
    def __missing__(self, key: _KT) -> ASubscribableQueue[_VT]:
        v = self[key] = ASubscribableQueue()
        return v

    # def __delitem__(self, key: _KT) -> None:
    #     print("QueueDict.__delitem__")
    #     self.data.pop(key).close()


class ASubscribableDict(UserDict[_KT, _VT], Generic[_KT, _VT]):
    """Dict with async generator that yields values as they change"""

    def __init__(self, *args, **kwargs):
        self._queue: QueueDict[_KT, _VT] = QueueDict()
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
        self.end(key)

    async def end(self, key: _KT):
        """End all subscriptions for the key without removing the key

        The async generators returned by the method `subscribe()` for the key
        will return.

        The item for the key is still accessible as d[key]

        KeyError will not be raised

        """
        if q := self._queue.pop(key, None):
            await q.close()

    async def close(self) -> None:
        """End all subscriptions for all keys

        The all async generators returned by the method `subscribe()` for any
        key will return.

        No keys will be removed, i.e., d[key] still returns the item for the
        key.

        """
        while self._queue:
            _, q = self._queue.popitem()
            await q.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()
