from __future__ import annotations

import enum
from asyncio import Queue, Condition

from typing import (
    AsyncIterator,
    Generic,
    Literal,
    Optional,
    List,
    Tuple,
    TypeVar,
)


class _M(enum.Enum):
    # TODO: Using Enum as sentinel for now as suggested in
    # https://stackoverflow.com/a/60605919/7309855. It still has a problem. For
    # example, the type of yielded values in subscribe() is not correctly
    # inferred as _T.

    START = object()
    END = object()


_T = TypeVar("_T")


class PubSubItem(Generic[_T]):
    """Distribute items to subscribers

    A new subscriber immediately receives the latest item and then wait for new
    items.

    The order of the items is preserved.
    """

    def __init__(self):

        self._qs_out: List[Queue[Tuple[int, _T | Literal[_M.END]]]] = []
        self._last_enumerated: Tuple[
            int, _T | Literal[_M.START] | Literal[_M.END]
        ] = (-1, _M.START)

        self._last_item: _T | Literal[_M.START] = _M.START
        self._idx = -1

        self._closed: bool = False
        self._lock_close = Condition()

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
        if self._last_item is _M.START:
            raise LookupError
        return self._last_item

    async def subscribe(
        self,
        last: Optional[bool] = True,
    ) -> AsyncIterator[_T]:
        """Yield data as they are put

        If `last` is true, yield immediately the most recent data before
        waiting for new data.
        """
        q: Queue[Tuple[int, _T | Literal[_M.END]]] = Queue()

        self._qs_out.append(q)

        last_idx, last_item = self._last_enumerated

        if last_item is _M.END:
            return

        try:
            if last and last_item is not _M.START:
                yield last_item

            while True:
                idx, item = await q.get()
                if item is _M.END:
                    break
                if last_idx < idx:
                    yield item

        finally:
            self._qs_out.remove(q)

    async def close(self) -> None:
        """End gracefully"""
        async with self._lock_close:
            if self._closed:
                return
            self._closed = True
            await self._publish(_M.END)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()

    async def _publish(self, item: _T | Literal[_M.END]) -> None:
        self._idx += 1
        self._last_enumerated = (self._idx, item)
        for q in list(self._qs_out):  # list in case it changes
            await q.put(self._last_enumerated)
