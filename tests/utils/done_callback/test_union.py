import asyncio
import random
import time
from threading import Thread

import pytest

from nextline.utils import ThreadTaskDoneCallback, current_task_or_thread


def target(obj: ThreadTaskDoneCallback) -> None:
    """To run in a thread or task"""
    assert current_task_or_thread() == obj.register()
    delay = random.random() * 0.01
    time.sleep(delay)


async def atarget(obj: ThreadTaskDoneCallback) -> None:
    target(obj)


class Done:
    """A callback function"""

    def __init__(self) -> None:
        self.args = set[Thread | asyncio.Task]()

    def __call__(self, arg: Thread | asyncio.Task) -> None:
        self.args.add(arg)


@pytest.fixture()
def done() -> Done:
    """A callback function"""
    return Done()


def test_thread(done: Done) -> None:
    obj = ThreadTaskDoneCallback(done=done)
    t = Thread(target=target, args=(obj,))
    t.start()
    time.sleep(0.005)
    obj.close()
    assert {t} == done.args
    t.join()


async def test_task(done: Done) -> None:
    obj = ThreadTaskDoneCallback(done=done)
    t = asyncio.create_task(atarget(obj))
    await t
    await obj.aclose()
    assert {t} == done.args


def test_with_thread(done: Done) -> None:
    with ThreadTaskDoneCallback(done=done) as obj:
        t = Thread(target=target, args=(obj,))
        t.start()
        time.sleep(0.005)
    assert {t} == done.args
    t.join()


async def test_with_task(done: Done) -> None:
    async with ThreadTaskDoneCallback(done=done) as obj:
        t = asyncio.create_task(atarget(obj))
        await t
    assert {t} == done.args


def test_done_none_thread() -> None:
    with ThreadTaskDoneCallback() as obj:
        t = Thread(target=target, args=(obj,))
        t.start()
        time.sleep(0.005)
    assert not t.is_alive()
    t.join()


async def test_done_none_task() -> None:
    async with ThreadTaskDoneCallback() as obj:
        t = asyncio.create_task(atarget(obj))
        await asyncio.sleep(0)  # let the task be registered
    assert t.done()  # finished after exited
    await t
