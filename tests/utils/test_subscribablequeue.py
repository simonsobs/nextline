from __future__ import annotations
import asyncio
from string import ascii_uppercase

import pytest

from nextline.utils import SubscribableQueue, ThreadSafeAsyncioEvent, to_thread

from .aiterable import aiterable


def test_daemon():
    _ = SubscribableQueue()
    # The program shouldn't be blocked even when close() is not called.


@pytest.fixture()
def obj():
    y = SubscribableQueue()
    yield y
    y.close()


def test_close(obj):
    assert obj


def test_close_multiple_times(obj):
    obj.close()
    obj.close()


def test_get(obj: SubscribableQueue[int]):
    with pytest.raises(LookupError):
        obj.get()
    for item in range(5):
        obj.put(item)
        assert item == obj.get()


@pytest.mark.asyncio
@pytest.mark.parametrize("n_items", (0, 1, 2, 5))
@pytest.mark.parametrize("n_subscriptions", (0, 1, 2, 5))
async def test_subscribe(obj: SubscribableQueue[int], n_items, n_subscriptions):
    items = tuple(range(n_items))
    expected = [items] * n_subscriptions

    async def receive():
        return tuple([i async for i in obj.subscribe()])

    async def send():
        async for i in aiterable(items):
            obj.put(i)
        obj.close()

    *results, _ = await asyncio.gather(
        *(receive() for _ in range(n_subscriptions)),
        send(),
    )
    assert results == expected
    assert obj.nsubscriptions == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("n", (0, 1, 2, 5))
async def test_nsubscriptions(obj: SubscribableQueue[int], n):
    async def receive():
        return tuple([i async for i in obj.subscribe()])

    task = asyncio.gather(*(receive() for _ in range(n)))
    await asyncio.sleep(0)
    assert obj.nsubscriptions == n
    obj.close()
    await task
    assert obj.nsubscriptions == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("n_pre_items", (0, 1, 2, 5))
@pytest.mark.parametrize("n_items", (0, 1, 3))
@pytest.mark.parametrize("last", [True, False])
@pytest.mark.parametrize("n_subscriptions", (0, 1, 3))
async def test_last(
    obj: SubscribableQueue[int | str],
    n_pre_items: int,
    n_items: int,
    last: bool,
    n_subscriptions: int,
):
    pre_items = tuple(ascii_uppercase[:n_pre_items])
    items = tuple(range(n_items))

    expected = [pre_items[-1:] + items if last else items] * n_subscriptions

    async def receive():
        return tuple([i async for i in obj.subscribe(last=last)])

    async def send():
        async for i in aiterable(items):
            obj.put(i)
        obj.close()

    for i in pre_items:
        obj.put(i)

    await asyncio.sleep(0.001)

    *results, _ = await asyncio.gather(
        *(receive() for _ in range(n_subscriptions)),
        send(),
    )
    assert results == expected


@pytest.mark.parametrize("n_items", (0, 1, 3))
def test_put_after_close(obj: SubscribableQueue[int | str], n_items: int):
    items = tuple(range(n_items))
    for i in items:
        obj.put(i)
    obj.close()
    with pytest.raises(RuntimeError):
        obj.put("A")
    if items:
        assert obj.get() == items[-1]  # the last item is not replaced
    else:
        with pytest.raises(LookupError):
            obj.get()


@pytest.mark.asyncio
@pytest.mark.parametrize("n_items", (0, 1, 3))
async def test_subscribe_after_close(obj: SubscribableQueue[int], n_items: int):
    items = tuple(range(n_items))
    for i in items:
        obj.put(i)
    obj.close()
    await asyncio.sleep(0.001)

    async def receive():
        return tuple([i async for i in obj.subscribe()])

    results = await receive()
    assert results == ()  # empty


@pytest.mark.asyncio
@pytest.mark.parametrize("at", (0, 2, 4))
async def test_break(obj: SubscribableQueue[int], at: int):
    items = tuple(range(5))
    expected = items[: items.index(at)]

    async def receive():
        ret = []
        assert obj.nsubscriptions == 0
        async for i in obj.subscribe():
            assert obj.nsubscriptions == 1
            if i == at:
                break
            ret.append(i)
        await asyncio.sleep(0.001)
        assert obj.nsubscriptions == 0  # the queue is closed
        return tuple(ret)

    async def send():
        async for i in aiterable(items):
            obj.put(i)
        obj.close()

    results, _ = await asyncio.gather(receive(), send())
    assert results == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("n_subscriptions", [0, 1, 2, 5, 50])
@pytest.mark.parametrize("n_pre_items", [0, 1, 2, 50])
@pytest.mark.parametrize("n_post_items", [0, 1, 2, 100])
async def test_thread(
    obj: SubscribableQueue[int],
    n_subscriptions: int,
    n_pre_items: int,
    n_post_items: int,
):
    """test if the issue is resolved
    https://github.com/simonsobs/nextline/issues/2

    """

    n_items = n_pre_items + n_post_items

    if n_subscriptions >= 50 and n_items >= 100:
        pytest.skip("nsubscribers >= 50 and nitems >= 100")

    pre_items = tuple(range(-n_pre_items, 0))
    post_items = tuple(range(n_post_items))
    items = pre_items + post_items
    assert len(items) == n_items

    event = ThreadSafeAsyncioEvent()

    async def receive():
        await event.wait()
        return tuple([i async for i in obj.subscribe()])

    def send():
        for i in pre_items:
            obj.put(i)
        event.set()
        for i in post_items:
            obj.put(i)
        obj.close()

    *results, _ = await asyncio.gather(
        *(receive() for _ in range(n_subscriptions)),
        to_thread(send),
    )
    for actual in results:
        if not actual:  # can be empty
            continue
        # print(actual[0])
        expected = items[items.index(actual[0]) :]  # no missing or duplicate
        assert actual == expected
