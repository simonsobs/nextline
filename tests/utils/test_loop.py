import asyncio

import pytest
from unittest.mock import Mock, call

from nextline.utils import ToLoop, to_thread


@pytest.fixture()
async def to_loop():
    y = ToLoop()
    yield y


def func(*_, **__):
    return "result"


async def test_loop(to_loop):
    func_ = Mock(wraps=func)
    ret = to_loop(func_, 1, a="a")
    assert "result" == ret
    assert call(1, a="a") == func_.call_args


async def test_thread(to_loop):
    def test():
        func_ = Mock(wraps=func)
        ret = to_loop(func_, 1, a="a")
        assert "result" == ret
        assert call(1, a="a") == func_.call_args

    await to_thread(test)


async def test_error_no_loop():
    def func():
        # in a thread without an event loop
        with pytest.raises(RuntimeError):
            _ = ToLoop()

    await to_thread(func)


async def test_error_loop_closed():
    async def create():
        return ToLoop()

    def test():

        # create to_loop() while the event loop is running
        to_loop = asyncio.run(create())

        # the loop is closed

        func_ = Mock(wraps=func)
        with pytest.raises(RuntimeError):
            to_loop(func_, 1, a="a")

        assert not func_.called

    await to_thread(test)
