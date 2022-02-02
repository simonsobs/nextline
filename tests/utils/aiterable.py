import asyncio


async def aiterable(iterable):
    '''Wrap iteralbe so can be used with "async for"'''
    for i in iterable:
        await asyncio.sleep(0)  # let other tasks run
        yield i
