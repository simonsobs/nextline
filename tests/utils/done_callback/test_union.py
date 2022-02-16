import time
import random

from threading import Thread
from asyncio import create_task

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
    obj.close()
    assert {t} == done.args
    t.join()


@pytest.mark.asyncio
async def test_task(done: Done):
    obj = ThreadTaskDoneCallback(done=done)
    t = create_task(atarget(obj))
    await t
    await obj.aclose()
    assert {t} == done.args
