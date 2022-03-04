import asyncio
from typing import AsyncGenerator, Iterable, Any


async def aiterable(iterable: Iterable) -> AsyncGenerator[Any, None]:
    '''Wrap iterable so can be used with "async for"'''
    for i in iterable:
        await asyncio.sleep(0)  # let other tasks run
        yield i
