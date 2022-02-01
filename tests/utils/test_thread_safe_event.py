import sys
import asyncio
import threading
import pytest

from nextline.utils import ThreadSafeAsyncioEvent


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_asyncio():
    obj = ThreadSafeAsyncioEvent()
    received = asyncio.Event()
    cleared = asyncio.Event()

    assert not obj.is_set()

    async def send():
        obj.set()
        assert obj.is_set()
        await received.wait()
        obj.clear()
        assert not obj.is_set()
        cleared.set()

    async def receive():
        await obj.wait()
        received.set()
        await cleared.wait()
        assert not obj.is_set()

    await asyncio.gather(send(), receive())


##__________________________________________________________________||
@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")
@pytest.mark.asyncio
async def test_thread():
    obj = ThreadSafeAsyncioEvent()
    received = threading.Event()
    cleared = threading.Event()

    assert not obj.is_set()

    def send():
        obj.set()
        assert obj.is_set()
        received.wait()
        obj.clear()
        assert not obj.is_set()
        cleared.set()

    async def receive():
        await obj.wait()
        received.set()
        await asyncio.to_thread(cleared.wait)
        assert not obj.is_set()

    await asyncio.gather(asyncio.to_thread(send), receive())


##__________________________________________________________________||
