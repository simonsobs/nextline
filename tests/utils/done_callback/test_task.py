import time
import random
import asyncio
import threading

from nextline.utils import TaskDoneCallback

import pytest
from unittest.mock import Mock


async def target(obj: TaskDoneCallback):
    assert asyncio.current_task() == obj.register()
    delay = random.random() * 0.01
    await asyncio.sleep(delay)


class Done:
    """A callback function"""

    def __init__(self):
        self.args = set()

    def __call__(self, arg):
        self.args.add(arg)


@pytest.fixture()
def done():
    """A callback function"""
    yield Done()


async def test_aclose(done: Done):
    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target(obj))
    await t
    await obj.aclose()
    assert {t} == done.args


async def test_async_with(done: Done):
    async with TaskDoneCallback(done=done) as obj:
        t = asyncio.create_task(target(obj))
        await t
    assert {t} == done.args


def test_asyncio_run_close(done: Done):
    obj = TaskDoneCallback(done=done)
    asyncio.run(target(obj))
    obj.close()
    assert 1 == len(done.args)


def test_asyncio_run_with(done: Done):
    with TaskDoneCallback(done=done) as obj:
        asyncio.run(target(obj))
    assert 1 == len(done.args)


def test_thread(done: Done):
    event = threading.Event()

    def f(obj: TaskDoneCallback):
        asyncio.run(target(obj))
        event.set()

    with TaskDoneCallback(done=done) as obj:
        t = threading.Thread(target=f, args=(obj,))
        t.start()
        event.wait()

    assert 1 == len(done.args)
    t.join()


async def test_register_arg(done: Done):
    async def target():
        delay = random.random() * 0.01
        await asyncio.sleep(delay)

    async with TaskDoneCallback(done=done) as obj:
        t = asyncio.create_task(target())

        # manually provide the task object
        assert t == obj.register(t)

        await t

    assert {t} == done.args


@pytest.mark.parametrize("n_tasks", [0, 1, 2, 5, 10])
async def test_multiple(n_tasks: int, done: Done):

    async with TaskDoneCallback(done=done) as obj:
        tasks = {asyncio.create_task(target(obj)) for _ in range(n_tasks)}
        await asyncio.gather(*tasks)

    assert tasks == done.args


async def test_raise_aclose_from_task(done: Done):
    async def target(obj: TaskDoneCallback):
        obj.register()
        delay = random.random() * 0.01
        time.sleep(delay)
        await obj.aclose()

    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target(obj))

    with pytest.raises(RuntimeError):
        await t


async def test_raise_close_from_task(done: Done):
    async def target(obj: TaskDoneCallback):
        obj.register()
        delay = random.random() * 0.01
        time.sleep(delay)
        obj.close()

    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target(obj))

    with pytest.raises(RuntimeError):
        await t


async def test_raise_in_done():
    done = Mock(side_effect=ValueError)
    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target(obj))

    await t

    with pytest.raises(ValueError):
        await obj.aclose()


async def test_done_none():
    async with TaskDoneCallback() as obj:
        t = asyncio.create_task(target(obj))
        await asyncio.sleep(0)  # let the task be registered
    assert t.done()  # finished after exited
    await t
