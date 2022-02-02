import sys
import asyncio
import time

import pytest

from nextline.utils import QueueDist, ThreadSafeAsyncioEvent

from .aiterable import aiterable


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_daemon():
    _ = QueueDist()
    # The program shouldn't be blocked even when close() is not called.


##__________________________________________________________________||
@pytest.fixture()
async def obj():
    y = QueueDist()
    yield y
    await y.close()


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_open_close(obj):
    assert obj


@pytest.mark.asyncio
async def test_close_multiple_times(obj):
    await obj.close()
    await obj.close()


async def async_send(obj, items):
    async for i in aiterable(items):
        obj.put(i)


async def async_receive(obj):
    return [i async for i in obj.subscribe()]


@pytest.mark.asyncio
async def test_subscribe(obj):
    items = list(range(10))
    task_receive_1 = asyncio.create_task(async_receive(obj))
    task_receive_2 = asyncio.create_task(async_receive(obj))
    task_send = asyncio.create_task(async_send(obj, items))
    await task_send
    results = await asyncio.gather(task_receive_1, task_receive_2, obj.close())
    result1, result2, *_ = results
    assert items == result1
    assert items == result2
    assert obj.nsubscriptions == 0


@pytest.mark.asyncio
async def test_recive_the_most_recent_item(obj):

    task_receive_1 = asyncio.create_task(async_receive(obj))
    await asyncio.sleep(0)  # let task_receive_1 start

    pre_items = ["A", "B", "C"]
    for i in pre_items:
        obj.put(i)

    time.sleep(0.1)

    task_receive_2 = asyncio.create_task(async_receive(obj))

    items = list(range(10))
    task_send = asyncio.create_task(async_send(obj, items))

    await task_send
    await obj.close()
    assert [*pre_items, *items] == await task_receive_1

    # receive 'C', which was put before task_receive_2 started
    assert [pre_items[-1], *items] == await task_receive_2


@pytest.mark.asyncio
async def test_subscribe_after_end(obj):
    # Note: This test might be unnecessary. It is more useful to test
    # what happens if subscribed after closed.

    items = list(range(10))
    task_send = asyncio.create_task(async_send(obj, items))
    await task_send
    await obj.close()

    task_receive = asyncio.create_task(async_receive(obj))
    await task_receive


async def async_receive_with_break(obj, at=None):
    ret = []
    async for i in obj.subscribe():
        if i == at:
            break
        ret.append(i)
    return ret


@pytest.mark.asyncio
async def test_break(obj):
    items = list(range(10))
    at = 5
    task_receive_1 = asyncio.create_task(async_receive_with_break(obj, at))
    task_receive_2 = asyncio.create_task(async_receive(obj))
    task_send = asyncio.create_task(async_send(obj, items))
    await task_send
    assert items[: items.index(at)] == await task_receive_1
    results = await asyncio.gather(task_receive_2, obj.close())
    result2, *_ = results
    assert items == result2
    assert obj.nsubscriptions == 0

##__________________________________________________________________||
nsubscribers = [0, 1, 2, 5, 50]
pre_nitems = [0, 1, 2, 50]
post_nitems = [0, 1, 2, 100]


@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread() ")
@pytest.mark.parametrize("post_nitems", post_nitems)
@pytest.mark.parametrize("pre_nitems", pre_nitems)
@pytest.mark.parametrize("nsubscribers", nsubscribers)
@pytest.mark.asyncio
async def test_thread(obj, nsubscribers, pre_nitems, post_nitems):
    """test if the issue is resovled
    https://github.com/simonsobs/nextline/issues/2

    """

    nitems = pre_nitems + post_nitems

    if nsubscribers >= 50 and nitems >= 100:
        pytest.skip("nsubscribers >= 50 and nitems >= 100")

    async def subscribe(obj, event):
        await event.wait()
        items = []
        async for i in obj.subscribe():
            items.append(i)
        return items

    def send(obj, pre_items, event, post_items, event_end):
        for i in pre_items:
            obj.put(i)
        event.set()
        for i in post_items:
            obj.put(i)
        event_end.set()

    async def close(obj, event_end):
        await event_end.wait()
        await obj.close()

    items = list(range(nitems))
    pre_items = items[:pre_nitems]
    post_items = items[pre_nitems:]

    event = ThreadSafeAsyncioEvent()
    event_end = ThreadSafeAsyncioEvent()

    coro = asyncio.to_thread(
        send, obj, pre_items, event, post_items, event_end
    )
    task_send = asyncio.create_task(coro)

    tasks_subscribe = []
    for i in range(nsubscribers):
        coro = subscribe(obj, event)
        task = asyncio.create_task(coro)
        tasks_subscribe.append(task)

    coro = close(obj, event_end)
    task_close = asyncio.create_task(coro)

    results = await asyncio.gather(*tasks_subscribe, task_send, task_close)
    for actual in results[:nsubscribers]:
        if not actual:  # can be empty
            continue
        # print(actual[0])
        expected = items[items.index(actual[0]) :]  # no missing or duplicate
        # items from the first
        # received item
        assert actual == expected


##__________________________________________________________________||
