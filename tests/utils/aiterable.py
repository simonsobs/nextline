import asyncio
from typing import AsyncIterable, Iterable


async def aiterable(iterable: Iterable) -> AsyncIterable:
    '''Wrap iterable so can be used with "async for"'''
    for i in iterable:
        await asyncio.sleep(0)  # let other tasks run
        yield i
