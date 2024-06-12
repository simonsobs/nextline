import enum
from asyncio import Condition, Queue
from collections.abc import AsyncIterator
from typing import Generic, Optional, TypeVar

# Use Enum with one object as sentinel as suggested in
# https://stackoverflow.com/a/60605919/7309855


class _Start(enum.Enum):
    '''Sentinel to indicate no item has been published yet.'''

    START = object()


class _End(enum.Enum):
    '''Sentinel to indicate no more item will be published.'''

    END = object()


_START = _Start.START
_END = _End.END


_T = TypeVar("_T")


# TODO: An Enum sentinel ans a generic type don't perfectly work together. For
# example, the type of yielded values in subscribe() is not correctly inferred
# as _T.


class PubSubItem(Generic[_T]):
    '''Distribute items to asynchronous subscribers.

    Example:

    Define items to distribute:

    >>> items = ['2', '1', 'a', 'b', 'c']

    To demonstrate the "last" option of the method `subscribe()`, we distribute
    the first two items ("2" and "1") before starting subscribers. Subscribers
    with the "last" option "True" will immediately receive the most recent
    distributed item ("1") and then wait for new items. Subscribers with the
    "last" option "False" will wait for new items only.

    Define two subscribers, one with the "last" option "True" and the other with
    the "last" option "False":

    >>> async def subscriber_with_last(obj):
    ...     return [i async for i in obj.subscribe(last=True)]

    >>> async def subscriber_without_last(obj):
    ...     return [i async for i in obj.subscribe(last=False)]

    Define two distributors, one that distributes the first two items and the
    other that distributes the rest of the items:

    >>> async def distributor_first_two(obj):
    ...     for i in items[:2]:
    ...         await obj.publish(i)

    >>> async def distributor_rest(obj):
    ...     for i in items[2:]:
    ...         await obj.publish(i)
    ...     await obj.close()

    The second distributor calls the method `close()` to end the subscriptions.
    The method `subscribe()` will return when the method `close()` is called.

    The class can be instantiated without a running asyncio event loop:

    >>> obj = PubSubItem()

    Define the asynchronous main function:

    >>> async def main():
    ...     # Run the first distributor.
    ...     await distributor_first_two(obj)
    ...
    ...     # Run the two subscribers and the second distributor.
    ...     received1, received2, _ = await asyncio.gather(
    ...         subscriber_with_last(obj),
    ...         subscriber_without_last(obj),
    ...         distributor_rest(obj),
    ...     )
    ...
    ...     # Print the received items.
    ...     print(received1)
    ...     print(received2)

    Run the main function:

    >>> import asyncio
    >>> asyncio.run(main())
    ['1', 'a', 'b', 'c']
    ['a', 'b', 'c']

    '''

    def __init__(self) -> None:
        self._qs_out = list[Queue[tuple[int, _T | _End]]]()
        self._last_enumerated: tuple[int, _T | _Start | _End] = (-1, _START)

        self._last_item: _T | _Start = _START
        self._idx = -1

        self._closed: bool = False
        self._lock_close: Condition | None = None

    @property
    def nsubscriptions(self) -> int:
        """The number of the subscribers"""
        return len(self._qs_out)

    async def publish(self, item: _T) -> None:
        """Send data to subscribers"""
        if self._closed:
            raise RuntimeError(f"{self} is closed.")
        self._last_item = item
        await self._publish(item)

    def latest(self) -> _T:
        """Most recent data that have been published"""
        if self._last_item is _START:
            raise LookupError
        return self._last_item

    async def subscribe(self, last: Optional[bool] = True) -> AsyncIterator[_T]:
        """Yield data as they are put

        If `last` is true, yield immediately the most recent data before
        waiting for new data.
        """
        q = Queue[tuple[int, _T | _End]]()

        self._qs_out.append(q)

        try:
            last_idx, last_item = self._last_enumerated

            if last_item is _END:
                return

            if last and last_item is not _START:
                yield last_item

            while True:
                idx, item = await q.get()
                if item is _END:
                    break
                if last_idx < idx:
                    yield item

        finally:
            self._qs_out.remove(q)

    async def close(self) -> None:
        """End gracefully"""
        self._lock_close = self._lock_close or Condition()
        async with self._lock_close:
            if self._closed:
                return
            self._closed = True
            await self._publish(_END)

    async def __aenter__(self) -> "PubSubItem[_T]":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore
        del exc_type, exc_value, traceback
        await self.close()

    async def _publish(self, item: _T | _End) -> None:
        self._idx += 1
        self._last_enumerated = (self._idx, item)
        for q in list(self._qs_out):  # list in case it changes
            await q.put(self._last_enumerated)
