import asyncio
from functools import partial

import pytest

from nextline.utils import ExcThread, to_thread
from nextline.utils import ThreadTaskIdComposer as IdComposer
from nextline.types import ThreadTaskId, ThreadNo, TaskNo


def assert_call(obj: IdComposer, expected: ThreadTaskId, has_id: bool = False):
    assert obj.has_id() is has_id
    assert obj.has_id() is has_id
    assert expected == obj()
    assert expected == obj()
    assert obj.has_id()


async def async_assert_call(
    obj: IdComposer, expected: ThreadTaskId, has_id: bool = False
):
    assert obj.has_id() is has_id
    assert obj.has_id() is has_id
    await asyncio.sleep(0)
    assert expected == obj()
    await asyncio.sleep(0)
    assert expected == obj()
    assert obj.has_id()


@pytest.fixture()
def obj():
    y = IdComposer()
    yield y


def test_compose(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected)

    obj.reset()

    assert_call(obj, expected, True)


def test_threads(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected)

    expected = ThreadTaskId(ThreadNo(2), None)
    t = ExcThread(target=assert_call, args=(obj, expected))
    t.start()
    t.join()

    expected = ThreadTaskId(ThreadNo(3), None)
    t = ExcThread(target=assert_call, args=(obj, expected))
    t.start()
    t.join()

    obj.reset()

    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected, True)

    expected = ThreadTaskId(ThreadNo(1), None)
    t = ExcThread(target=assert_call, args=(obj, expected))
    t.start()
    t.join()

    expected = ThreadTaskId(ThreadNo(2), None)
    t = ExcThread(target=assert_call, args=(obj, expected))
    t.start()
    t.join()


async def test_async_coroutine(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    assert_call(obj, expected)

    # run in the same task
    await async_assert_call(obj, expected, True)
    await async_assert_call(obj, expected, True)

    obj.reset()

    await async_assert_call(obj, expected, True)
    await async_assert_call(obj, expected, True)


async def test_async_tasks(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    assert_call(obj, expected)

    expected = ThreadTaskId(ThreadNo(1), TaskNo(2))
    t = asyncio.create_task(async_assert_call(obj, expected))
    await t

    expected = ThreadTaskId(ThreadNo(1), TaskNo(3))
    t = asyncio.create_task(async_assert_call(obj, expected))
    await t

    obj.reset()

    expected = ThreadTaskId(
        ThreadNo(1), TaskNo(1)
    )  # the old id is still there
    assert_call(obj, expected, True)

    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))  # task no is reset to 1
    t = asyncio.create_task(async_assert_call(obj, expected))
    await t

    expected = ThreadTaskId(ThreadNo(1), TaskNo(2))
    t = asyncio.create_task(async_assert_call(obj, expected))
    await t


async def test_async_tasks_gather(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    assert_call(obj, expected)

    expected = ThreadTaskId(ThreadNo(1), TaskNo(2))
    t1 = asyncio.create_task(async_assert_call(obj, expected))
    expected = ThreadTaskId(ThreadNo(1), TaskNo(3))
    t2 = asyncio.create_task(async_assert_call(obj, expected))
    aws = {t1, t2}
    await asyncio.gather(*aws)

    obj.reset()

    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    assert_call(obj, expected, True)

    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    t1 = asyncio.create_task(async_assert_call(obj, expected))
    expected = ThreadTaskId(ThreadNo(1), TaskNo(2))
    t2 = asyncio.create_task(async_assert_call(obj, expected))
    aws = {t1, t2}
    await asyncio.gather(*aws)


def test_async_asyncio_run(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected)

    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    asyncio.run(async_assert_call(obj, expected))

    obj.reset()

    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected, True)

    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    asyncio.run(async_assert_call(obj, expected))


async def test_async_asyncio_to_thread(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    assert_call(obj, expected)

    expected = ThreadTaskId(ThreadNo(2), None)
    await to_thread(partial(assert_call, obj, expected))

    expected = ThreadTaskId(
        ThreadNo(2), None
    )  # to_thread uses the same thread
    await to_thread(partial(assert_call, obj, expected, True))

    obj.reset()

    expected = ThreadTaskId(ThreadNo(1), TaskNo(1))
    assert_call(obj, expected, True)

    expected = ThreadTaskId(
        ThreadNo(2), None
    )  # to_thread uses the same thread
    await to_thread(partial(assert_call, obj, expected, True))

    expected = ThreadTaskId(
        ThreadNo(2), None
    )  # to_thread uses the same thread
    await to_thread(partial(assert_call, obj, expected, True))


async def async_nested(obj: IdComposer, expected_thread_id):
    expected1 = ThreadTaskId(expected_thread_id, TaskNo(1))
    assert_call(obj, expected1)
    await async_assert_call(obj, expected1, True)

    expected2 = ThreadTaskId(expected_thread_id, TaskNo(2))
    t1 = asyncio.create_task(async_assert_call(obj, expected2))
    expected3 = ThreadTaskId(expected_thread_id, TaskNo(3))
    t2 = asyncio.create_task(async_assert_call(obj, expected3))
    aws = {t1, t2}
    await asyncio.gather(*aws)


def nested(obj: IdComposer, expected_thread_id):
    expected = ThreadTaskId(expected_thread_id, None)
    assert_call(obj, expected)

    asyncio.run(async_nested(obj, expected_thread_id))


def test_nested(obj: IdComposer):
    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected)

    expected_thread_id = 2
    t = ExcThread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()

    expected_thread_id = 3
    t = ExcThread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()

    obj.reset()

    expected = ThreadTaskId(ThreadNo(1), None)
    assert_call(obj, expected, True)

    expected_thread_id = 1  # reset to 1
    t = ExcThread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()

    expected_thread_id = 2
    t = ExcThread(target=nested, args=(obj, expected_thread_id))
    t.start()
    t.join()
