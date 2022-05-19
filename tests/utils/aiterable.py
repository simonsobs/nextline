import asyncio
from typing import AsyncIterator, Iterable, TypeVar

T = TypeVar("T")


async def aiterable(iterable: Iterable[T]) -> AsyncIterator[T]:
    '''Wrap iterable so can be used with "async for"'''
    for i in iterable:
        await asyncio.sleep(0)  # let other tasks run
        yield i
