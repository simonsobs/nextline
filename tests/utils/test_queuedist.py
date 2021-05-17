import asyncio
import threading
from functools import partial
import time

import pytest

from nextline.utils import (
    QueueDist,
    ThreadSafeAsyncioEvent
)

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_daemon():
    obj = QueueDist()
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
    for i in items:
        await asyncio.sleep(0) # let other tasks run
        obj.put(i)
    obj.put(None)

async def async_receive(obj):
    items = []
    async for i in obj.subscribe():
        if i is None:
            break
        items.append(i)
    return items

@pytest.mark.asyncio
async def test_subscribe(obj):
    items = list(range(10))
    task_receive_1 = asyncio.create_task(async_receive(obj))
    task_receive_2 = asyncio.create_task(async_receive(obj))
    task_send = asyncio.create_task(async_send(obj, items))
    await task_send
    assert items == await task_receive_1
    assert items == await task_receive_2

@pytest.mark.asyncio
async def test_recive_the_most_recent_item(obj):

    task_receive_1 = asyncio.create_task(async_receive(obj))
    await asyncio.sleep(0) # let task_receive_1 start

    pre_items = ['A', 'B', 'C']
    for i in pre_items:
        obj.put(i)

    time.sleep(0.1)

    task_receive_2 = asyncio.create_task(async_receive(obj))

    items = list(range(10))
    task_send = asyncio.create_task(async_send(obj, items))

    await task_send
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

    task_receive = asyncio.create_task(async_receive(obj))
    await task_receive

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_thread(obj):
    '''test if the issue is resovled
    https://github.com/simonsobs/nextline/issues/2

    not perfect. needs to be revised.
    '''

    def send(obj, event, items):
        for i in items:
            obj.put(i)
            # time.sleep(0.00001)
        obj.put(None)

    async def set_event(obj, event, at=5):
        async for i in obj.subscribe():
            if i is None or i >= at:
                event.set()
            if i is None:
                break
        return

    items = list(range(2000))
    event = ThreadSafeAsyncioEvent()
    send = partial(send, obj, event, items)
    t = threading.Thread(target=send, daemon=True)
    t.start()

    task_set_event = asyncio.create_task(set_event(obj, event))

    ntasks = 5
    tasks = []

    await event.wait()

    for i in range(ntasks):
        tasks.append(asyncio.create_task(async_receive(obj)))

    for i in range(ntasks):
        received = await tasks[i]
        if received:
            assert received == items[items.index(received[0]):]

    t.join()

##__________________________________________________________________||
