import sys
import asyncio
import threading
from functools import partial

import pytest

from nextline.utils import UniqThreadTaskIdComposer as IdComposer
from nextline.utils.types import ThreadTaskId


##__________________________________________________________________||
@pytest.fixture(autouse=True)
def wrap_thread(monkeypatch):
    """Replace threading.Thread with nextline.utils.ExcThread"""

    from nextline.utils import ExcThread

    monkeypatch.setattr(threading, "Thread", ExcThread)

    yield


##__________________________________________________________________||
def assert_call(obj: IdComposer, expected: ThreadTaskId):
    assert expected == obj()
    assert expected == obj()


async def async_assert_call(obj: IdComposer, expected: ThreadTaskId):
    await asyncio.sleep(0)
    assert expected == obj()
    await asyncio.sleep(0)
    assert expected == obj()


##__________________________________________________________________||
@pytest.fixture()
def obj():
    y = IdComposer()
    yield y


##__________________________________________________________________||
def test_compose(obj: IdComposer):
    expected = (1, None)
    assert_call(obj, expected)


def test_threads(obj: IdComposer):
    expected = (1, None)
    assert_call(obj, expected)

    expected = (2, None)
    t = threading.Thread(target=assert_call, args=(obj, expected))
    t.start()
    t.join()

    expected = (3, None)
    t = threading.Thread(target=assert_call, args=(obj, expected))
    t.start()
    t.join()


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_async_coroutine(obj: IdComposer):
    expected = (1, 1)
    assert_call(obj, expected)

    # run in the same task
    await async_assert_call(obj, expected)
    await async_assert_call(obj, expected)


@pytest.mark.asyncio
async def test_async_tasks(obj: IdComposer):
    expected = (1, 1)
    assert_call(obj, expected)

    expected = (1, 2)
    t = asyncio.create_task(async_assert_call(obj, expected))
    await t

    expected = (1, 3)
    t = asyncio.create_task(async_assert_call(obj, expected))
    await t


@pytest.mark.asyncio
async def test_async_tasks_gather(obj: IdComposer):
    expected = (1, 1)
    assert_call(obj, expected)

    expected = (1, 2)
    t1 = asyncio.create_task(async_assert_call(obj, expected))
    expected = (1, 3)
    t2 = asyncio.create_task(async_assert_call(obj, expected))
    aws = {t1, t2}
    await asyncio.gather(*aws)


def test_async_asyncio_run(obj: IdComposer):
    expected = (1, None)
    assert_call(obj, expected)

    expected = (1, 1)
    asyncio.run(async_assert_call(obj, expected))


@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")
@pytest.mark.asyncio
async def test_async_asyncio_to_thread(obj: IdComposer):
    expected = (1, 1)
    assert_call(obj, expected)

    expected = (2, None)
    await asyncio.to_thread(partial(assert_call, obj, expected))

    expected = (2, None)
    await asyncio.to_thread(partial(assert_call, obj, expected))


##__________________________________________________________________||
async def async_nested(obj: IdComposer, expected_thread_id):
    expected1 = (expected_thread_id, 1)
    assert_call(obj, expected1)
    await async_assert_call(obj, expected1)

    expected2 = (expected_thread_id, 2)
    t1 = asyncio.create_task(async_assert_call(obj, expected2))
    expected3 = (expected_thread_id, 3)
    t2 = asyncio.create_task(async_assert_call(obj, expected3))
    aws = {t1, t2}
    await asyncio.gather(*aws)


def nested(obj: IdComposer, expected_thread_id):
    expected = (expected_thread_id, None)
    assert_call(obj, expected)

    asyncio.run(async_nested(obj, expected_thread_id))


def test_nested(obj: IdComposer):
    expected = (1, None)
    assert_call(obj, expected)

    expected_thread_id = 2
    t = threading.Thread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()

    expected_thread_id = 3
    t = threading.Thread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()


##__________________________________________________________________||
