import time
import random
import asyncio
import threading

from nextline.utils import TaskDoneCallback

import pytest
from unittest.mock import Mock


async def target(obj: TaskDoneCallback):
    obj.register()
    delay = random.random() * 0.01
    time.sleep(delay)


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


@pytest.mark.asyncio
async def test_one(done: Done):
    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target(obj))
    await t
    await obj.aclose()
    assert {t} == done.args


def test_asyncio_run(done: Done):
    obj = TaskDoneCallback(done=done)
    asyncio.run(target(obj))
    obj.close()
    assert 1 == len(done.args)


def test_thread(done: Done):
    event = threading.Event()

    def f(obj: TaskDoneCallback):
        asyncio.run(target(obj))
        event.set()

    obj = TaskDoneCallback(done=done)
    t = threading.Thread(target=f, args=(obj,))
    t.start()
    event.wait()
    obj.close()
    assert 1 == len(done.args)
    t.join()


@pytest.mark.asyncio
async def test_register_arg(done: Done):
    async def target():
        delay = random.random() * 0.01
        await asyncio.sleep(delay)

    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target())

    # manually provide the task object
    obj.register(t)

    await t
    await obj.aclose()
    assert {t} == done.args


@pytest.mark.parametrize("ntasks", [0, 1, 2, 5, 10])
@pytest.mark.asyncio
async def test_multiple(ntasks: int, done: Done):

    obj = TaskDoneCallback(done=done)

    tasks = {asyncio.create_task(target(obj)) for _ in range(ntasks)}
    await asyncio.gather(*tasks)

    await obj.aclose()
    assert tasks == done.args


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_raise_in_done():
    done = Mock(side_effect=ValueError)
    obj = TaskDoneCallback(done=done)
    t = asyncio.create_task(target(obj))

    await t

    with pytest.raises(ValueError):
        await obj.aclose()
