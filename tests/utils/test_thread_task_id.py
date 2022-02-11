import sys
import asyncio
import threading
from functools import partial

import pytest

from nextline.utils import UniqThreadTaskIdComposer
from nextline.utils.types import ThreadTaskId


##__________________________________________________________________||
@pytest.fixture(autouse=True)
def wrap_thread(monkeypatch):
    """Replace threading.Thread with nextline.utils.ExcThread"""

    from nextline.utils import ExcThread

    monkeypatch.setattr(threading, "Thread", ExcThread)

    yield


##__________________________________________________________________||
def assert_func(obj: UniqThreadTaskIdComposer, expected: ThreadTaskId):
    assert expected == obj.compose()
    assert expected == obj.compose()


async def async_assert_func(obj: UniqThreadTaskIdComposer, expected: ThreadTaskId):
    return assert_func(obj, expected)


##__________________________________________________________________||
@pytest.fixture()
def obj():
    y = UniqThreadTaskIdComposer()
    yield y


##__________________________________________________________________||
def test_compose(obj: UniqThreadTaskIdComposer):
    expected = (1, None)
    assert_func(obj, expected)


def test_threads(obj: UniqThreadTaskIdComposer):
    expected = (1, None)
    assert_func(obj, expected)

    expected = (2, None)
    t = threading.Thread(target=assert_func, args=(obj, expected))
    t.start()
    t.join()
    obj.exited(expected)

    expected = (3, None)
    t = threading.Thread(target=assert_func, args=(obj, expected))
    t.start()
    t.join()
    obj.exited(expected)


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_async_coroutine(obj: UniqThreadTaskIdComposer):
    expected = (1, 1)
    assert_func(obj, expected)

    # run in the same task
    await async_assert_func(obj, expected)
    await async_assert_func(obj, expected)


@pytest.mark.asyncio
async def test_async_tasks(obj: UniqThreadTaskIdComposer):
    expected = (1, 1)
    assert_func(obj, expected)

    expected = (1, 2)
    t = asyncio.create_task(async_assert_func(obj, expected))
    await t
    obj.exited(expected)

    expected = (1, 3)
    t = asyncio.create_task(async_assert_func(obj, expected))
    await t
    obj.exited(expected)


@pytest.mark.asyncio
async def test_async_tasks_gather(obj: UniqThreadTaskIdComposer):
    expected = (1, 1)
    assert_func(obj, expected)

    expected = (1, 2)
    t1 = asyncio.create_task(async_assert_func(obj, expected))
    expected = (1, 3)
    t2 = asyncio.create_task(async_assert_func(obj, expected))
    aws = {t1, t2}
    await asyncio.gather(*aws)


def test_async_asyncio_run(obj: UniqThreadTaskIdComposer):
    expected = (1, None)
    assert_func(obj, expected)

    expected = (1, 1)
    asyncio.run(async_assert_func(obj, expected))


@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")
@pytest.mark.asyncio
async def test_async_asyncio_to_thread(obj: UniqThreadTaskIdComposer):
    expected = (1, 1)
    assert_func(obj, expected)

    expected = (2, None)
    await asyncio.to_thread(partial(assert_func, obj, expected))
    obj.exited(expected)

    expected = (3, None)
    await asyncio.to_thread(partial(assert_func, obj, expected))
    obj.exited(expected)


##__________________________________________________________________||
async def async_nested(obj: UniqThreadTaskIdComposer, expected_thread_id):
    expected = (expected_thread_id, 1)
    assert_func(obj, expected)
    await async_assert_func(obj, expected)

    expected = (expected_thread_id, 2)
    t1 = asyncio.create_task(async_assert_func(obj, expected))
    expected = (expected_thread_id, 3)
    t2 = asyncio.create_task(async_assert_func(obj, expected))
    aws = {t1, t2}
    await asyncio.gather(*aws)
    obj.exited((expected_thread_id, 2))
    obj.exited((expected_thread_id, 3))


def nested(obj: UniqThreadTaskIdComposer, expected_thread_id):
    expected = (expected_thread_id, None)
    assert_func(obj, expected)

    asyncio.run(async_nested(obj, expected_thread_id))
    obj.exited((expected_thread_id, 1))


def test_nested(obj: UniqThreadTaskIdComposer):
    expected = (1, None)
    assert_func(obj, expected)

    expected_thread_id = 2
    t = threading.Thread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()
    obj.exited((expected_thread_id, None))

    expected_thread_id = 3
    t = threading.Thread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()
    obj.exited((expected_thread_id, None))


##__________________________________________________________________||
