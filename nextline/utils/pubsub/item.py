import asyncio
import enum
from collections.abc import AsyncIterator
from typing import Any, Generic, TypeAlias, TypeVar

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


_Item = TypeVar('_Item')


# TODO: An Enum sentinel ans a generic type don't perfectly work together. For
# example, the type of yielded values in subscribe() is not correctly inferred
# as _Item.


Enumerated: TypeAlias = tuple[int, _Item | _End]
LastEnumerated: TypeAlias = tuple[int, _Item | _End | _Start]


class PubSubItem(Generic[_Item]):
    '''Distribute items to multiple asynchronous subscribers.

    Parameters
    ----------
    cache
        If `True`, all items are cached and new subscribers receive all items
        and wait for new items. The default is `False`.


    Examples
    --------

    1. Basic usage

    The first example shows a basic usage of the class, in which items are
    distributed to two subscribers.

    Items to distribute, terminated by `None`:

    >>> items = ['a', 'b', 'c', 'd', 'e', None]

    An instance of this class:

    >>> obj = PubSubItem()

    A function to distribute items:

    >>> async def send(obj, items):
    ...    for i in items:
    ...        await obj.publish(i)
    ...        await asyncio.sleep(0)

    A function to subscribe to items:

    >>> async def receive(obj):
    ...     ret = []
    ...     async for i in obj.subscribe():
    ...         if i is None:
    ...             break
    ...         ret.append(i)
    ...     return ret

    Distribute the items to two subscribers:

    >>> async def main():
    ...     return await asyncio.gather(receive(obj), receive(obj), send(obj, items))

    >>> r1, r2, _ = asyncio.run(main())

    Both subscribers receive all items:

    >>> r1
    ['a', 'b', 'c', 'd', 'e']

    >>> r2
    ['a', 'b', 'c', 'd', 'e']

    2. The `last` option

    The `subscribe()` method has an optional argument `last`, which is `True`
    by default. The `last` option was irrelevant in the previous example
    because all subscriptions started before any item was distributed. When a
    subscription starts after the distribution has started, the `last` option
    becomes important. If the `last` option is `True`, the subscriber will
    immediately receive the most recent distributed item before waiting for new
    items. If the `last` option is `False`, the subscriber will wait for new
    items only.

    Items to distribute:

    >>> items = ['3', '2', '1', 'a', 'b', None]

    Create a new instance of the class:

    >>> obj = PubSubItem()

    Update `receive()` to replace the `obj` argument with an asynchronous iterator:

    >>> async def receive(it):
    ...     ret = []
    ...     async for i in it:
    ...         if i is None:
    ...             break
    ...         ret.append(i)
    ...     return ret

    Distribute the first three items, start two subscribers without the `last`
    option (default to `True`) and with the `last` option `False`, and distribute
    the rest of the items:


    >>> async def main():
    ...     await send(obj, items[:3])
    ...     return await asyncio.gather(
    ...         receive(obj.subscribe()),
    ...         receive(obj.subscribe(last=False)),
    ...         send(obj, items[3:]),
    ...     )

    >>> t, f, _ = asyncio.run(main())

    The first subscriber without the `last` option received the most recent
    item ("1") that was distributed before it started as well as the rest of
    the items ("a" and "b") distributed after it started:

    >>> t
    ['1', 'a', 'b']

    The second subscriber with the `last` option `False` received only the items
    distributed after it started:

    >>> f
    ['a', 'b']

    3. The `cache` option

    The `__init__()` and `subscribe()` methods have an optional argument
    `cache`. The default values are `False` for `__init__()`, and `True` for
    `subscribe()`. The `cache` option for `subscribe()` is relevant only if the
    `last` option is `True` and the `cache` option for `__init__()` is `True`.

    If the `cache` option for `__init__()` is `True`, all items are cached and
    new subscribers receive all items and wait for new items unless the `last`
    or `cache` option of `subscribe()` is `False`.

    Items to distribute:

    >>> items = ['3', '2', '1', 'a', 'b', None]

    Create a new instance of the class with the `cache` option `True`:

    >>> obj = PubSubItem(cache=True)

    Distribute the first three items, start three subscribers without options,
    with the `cache` option `False`, and with the `last` option `False`, and
    distribute the rest of the items:

    >>> async def main():
    ...     await send(obj, items[:3])
    ...     return await asyncio.gather(
    ...         receive(obj.subscribe()),
    ...         receive(obj.subscribe(cache=False)),
    ...         receive(obj.subscribe(last=False)),
    ...         send(obj, items[3:]),
    ...     )

    >>> r1, r2, r3, _ = asyncio.run(main())

    With no options to `subscribe()`, the first subscriber received all items:

    >>> r1
    ['3', '2', '1', 'a', 'b']

    With the `cache` option `False`, the second subscriber received the most
    recent item ("1") that was distributed before it started and the rest of
    the items.

    >>> r2
    ['1', 'a', 'b']

    With the `last` option `False`, the third subscriber received only the
    items distributed after it started:

    >>> r3
    ['a', 'b']


    '''

    def __init__(self, *, cache: bool = False) -> None:
        self._cache = list[Enumerated[_Item]]() if cache else None

        self._queues = list[asyncio.Queue[Enumerated[_Item]]]()
        self._last_enumerated: LastEnumerated[_Item] = (-1, _START)

        self._last_item: _Item | _Start = _START
        self._idx = -1

        self._closed: bool = False
        self._lock_close: asyncio.Condition | None = None

    @property
    def cache(self) -> bool:
        '''True if the cache is enabled, False otherwise.'''
        return self._cache is not None

    @property
    def closed(self) -> bool:
        '''True if the instance is closed, False otherwise.'''
        return self._closed

    @property
    def n_subscriptions(self) -> int:
        '''The number of the subscribers'''
        return len(self._queues)

    async def publish(self, item: _Item) -> None:
        '''Send data to subscribers'''
        if self._closed:
            raise RuntimeError(f'{self} is closed.')
        self._last_item = item
        await self._enumerate(item)

    def clear(self) -> None:
        '''Remove the last item and clear the cache if it is enabled'''
        if self._closed:
            raise RuntimeError(f'{self} is closed.')
        self._idx += 1
        self._last_enumerated = (self._idx, _START)
        self._last_item = _START
        if self._cache is not None:
            self._cache.clear()

    def latest(self) -> _Item:
        '''Most recent data that have been published'''
        if self._last_item is _START:
            raise LookupError
        return self._last_item

    async def subscribe(
        self, last: bool = True, cache: bool = True
    ) -> AsyncIterator[_Item]:
        '''Yield data as they are put after yielding, based on the options, old data.

        Parameters
        ----------
        last
            If `True`, yield the most recent data before waiting for new data.
            The default is `True`.
        cache
            This option is only relevant if the `last` option is `True` and the
            `cache` option of the class is `True`. The default is `True`. If
            `True`, yield all data that have been published so far before
            waiting for new data.
        '''

        # Copy these attributes as they can change after `yield` and `await`
        last_idx, last_item = self._last_enumerated
        cached = list(self._cache) if self._cache is not None else None

        if last_item is _END:
            return

        if not (last and cached):
            cache = False

        q = asyncio.Queue[Enumerated[_Item]]()
        self._queues.append(q)

        try:
            # Yield the old data from the first to the one before the most recent
            if cache and cached is not None:
                for idx, item in cached:
                    if not idx < last_idx:
                        break
                    if item is _END:
                        return  # pragma: no cover
                    yield item

            # Yield the most recent data
            if last and last_item is not _START:
                yield last_item

            # Yield new data as they arrive
            while True:
                idx, item = await q.get()
                if item is _END:
                    return
                if last_idx < idx:
                    yield item

        finally:
            self._queues.remove(q)

    async def aclose(self) -> None:
        '''Return all subscriptions and prevent new subscriptions.'''
        self._lock_close = self._lock_close or asyncio.Condition()
        async with self._lock_close:
            if self._closed:
                return
            self._closed = True
            await self._enumerate(_END)

    async def __aenter__(self) -> 'PubSubItem[_Item]':
        return self

    async def __aexit__(self, *_: Any, **__: Any) -> None:
        await self.aclose()

    async def _enumerate(self, item: _Item | _End) -> None:
        self._idx += 1
        self._last_enumerated = enumerated = (self._idx, item)
        if self._cache is not None:
            self._cache.append(enumerated)
        for q in list(self._queues):  # list in case it changes
            await q.put(enumerated)
