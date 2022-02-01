import sys
import asyncio

import pytest
from unittest.mock import AsyncMock

from nextline.utils import CoroutineRunner


##__________________________________________________________________||
@pytest.fixture()
async def obj():
    y = CoroutineRunner()
    yield y


@pytest.mark.asyncio
async def test_repr(obj):
    repr(obj)


@pytest.mark.asyncio
async def test_async(obj):
    afunc = AsyncMock()
    coro = afunc()
    task = obj.run(coro)
    await task
    assert 1 == afunc.await_count


@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")
@pytest.mark.asyncio
async def test_thread(obj):
    def func():
        afunc = AsyncMock()
        coro = afunc()
        ret = obj.run(coro)
        assert ret is None
        assert 1 == afunc.await_count

    await asyncio.to_thread(func)


##__________________________________________________________________||
@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")
@pytest.mark.asyncio
async def test_error_no_loop():
    def func():
        # in a thread without an event loop
        with pytest.raises(RuntimeError):
            _ = CoroutineRunner()

    await asyncio.to_thread(func)


@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")
@pytest.mark.asyncio
async def test_error_loop_closed():
    async def instantiate():
        obj = CoroutineRunner()
        return obj

    def func():

        # initialize the class while the event loop is running
        obj = asyncio.run(instantiate())

        # the loop is closed

        afunc = AsyncMock()
        coro = afunc()
        with pytest.raises(RuntimeError):
            obj.run(coro)

        assert 0 == afunc.await_count

    with pytest.warns(RuntimeWarning):
        # RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
        await asyncio.to_thread(func)
