from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Generic, Optional, TypeVar

from .item import PubSubItem

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class PubSub(Generic[_KT, _VT]):
    """Asynchronous message broker of the publish-subscribe pattern"""

    def __init__(self) -> None:
        self._queue = defaultdict[_KT, PubSubItem[_VT]](PubSubItem)

    def subscribe(self, key: _KT, last: Optional[bool] = True) -> AsyncIterator[_VT]:
        """Async iterator that yields values for the key as they are published

        Waits for new values and yields them as they are set. If `last` is
        true, yields immediately the latest value for the key before starting
        to wait. If the key doesn't exist, waits for the first value for the
        key; KeyError won't be raised.

        """
        return self._queue[key].subscribe(last=last)

    async def publish(self, key: _KT, value: _VT) -> None:
        """Yield the value in the generators"""
        await self._queue[key].publish(value)

    def latest(self, key: _KT) -> _VT:
        """Latest value for the key"""
        return self._queue[key].latest()

    async def end(self, key: _KT) -> None:
        """End all subscriptions for the key

        The async generators returned by the method `subscribe()` for the key
        will return.

        """
        if q := self._queue.pop(key, None):
            await q.close()

    async def close(self) -> None:
        """End all subscriptions for all keys

        All async generators returned by the method `subscribe()` for any key
        will return.

        """
        while self._queue:
            _, q = self._queue.popitem()
            await q.close()

    async def __aenter__(self) -> "PubSub[_KT, _VT]":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore
        del exc_type, exc_value, traceback
        await self.close()
