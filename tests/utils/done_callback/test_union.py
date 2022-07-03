import time
import random

from threading import Thread
import asyncio

import pytest


from nextline.utils import ThreadTaskDoneCallback, current_task_or_thread


def target(obj: ThreadTaskDoneCallback):
    """To run in a thread or task"""
    assert current_task_or_thread() == obj.register()
    delay = random.random() * 0.01
    time.sleep(delay)


async def atarget(obj: ThreadTaskDoneCallback):
    target(obj)


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


def test_thread(done: Done):
    obj = ThreadTaskDoneCallback(done=done)
    t = Thread(target=target, args=(obj,))
    t.start()
    time.sleep(0.005)
    obj.close()
    assert {t} == done.args
    t.join()


async def test_task(done: Done):
    obj = ThreadTaskDoneCallback(done=done)
    t = asyncio.create_task(atarget(obj))
    await t
    await obj.aclose()
    assert {t} == done.args


def test_with_thread(done: Done):
    with ThreadTaskDoneCallback(done=done) as obj:
        t = Thread(target=target, args=(obj,))
        t.start()
        time.sleep(0.005)
    assert {t} == done.args
    t.join()


async def test_with_task(done: Done):
    async with ThreadTaskDoneCallback(done=done) as obj:
        t = asyncio.create_task(atarget(obj))
        await t
    assert {t} == done.args


def test_done_none_thread():
    with ThreadTaskDoneCallback() as obj:
        t = Thread(target=target, args=(obj,))
        t.start()
        time.sleep(0.005)
    assert not t.is_alive()
    t.join()


async def test_done_none_task():
    async with ThreadTaskDoneCallback() as obj:
        t = asyncio.create_task(atarget(obj))
        await asyncio.sleep(0)  # let the task be registered
    assert t.done()  # finished after exited
    await t
