import asyncio
from string import ascii_lowercase

import pytest

from nextline.utils import SubscribableDict, to_thread

from .aiterable import aiterable


@pytest.fixture
def obj():
    y = SubscribableDict()
    yield y
    y.close()


@pytest.mark.asyncio
async def test_end(obj: SubscribableDict[str, str]):
    key = "A"

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        obj.end(key)

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == ()


@pytest.mark.asyncio
async def test_end_without_subscription(obj: SubscribableDict[str, str]):
    key = "A"
    obj.end(key)


@pytest.mark.asyncio
async def test_close(obj: SubscribableDict[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        for item in items:
            obj[key] = item
        obj.close()  # ends the subscription
        assert obj[key] == items[-1]  # the last item is still there

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.asyncio
async def test_clear(obj: SubscribableDict[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        obj.clear()  # doesn't end the subscription as no item hasn't been put
        for item in items:
            obj[key] = item
        obj.clear()  # ends the subscription
        assert key not in obj  # the item is deleted

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.asyncio
async def test_del(obj: SubscribableDict[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        with pytest.raises(KeyError):
            del obj[key]  # this doesn't end the subscription
        for item in items:
            obj[key] = item
        del obj[key]  # this ends the subscription
        assert key not in obj

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.asyncio
@pytest.mark.parametrize("last", [True, False])
async def test_last(obj: SubscribableDict[str, str], last: bool):
    key = "A"
    n_pre_items = 3
    n_items = 5
    pre_items = tuple(reversed(ascii_lowercase[-n_pre_items:]))
    items = tuple(ascii_lowercase[:n_items])
    expected = pre_items[-1:] + items if last else items

    for item in pre_items:
        obj[key] = item

    await asyncio.sleep(0.001)

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key, last=last)])

    async def put():
        await asyncio.sleep(0.001)
        for item in items:
            obj[key] = item
        del obj[key]

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == expected


@pytest.mark.asyncio
async def test_one_():
    obj: SubscribableDict[str, str] = SubscribableDict()

    key = "key_one"
    items = ["item_one", "item_two", "item_three"]

    async def subscribe(last=True):
        return [y async for y in obj.subscribe(key, last=last)]

    async def send():
        async for i in aiterable(items):
            obj[key] = i
            assert i == obj[key]
        assert 1 == len(obj)
        assert [key] == list(obj)
        del obj[key]
        assert 0 == len(obj)
        assert [] == list(obj)

    results = await asyncio.gather(subscribe(), subscribe(False), send())
    # NOTE: the effect of the option `last` is not tested
    assert items == results[0]
    assert items == results[1]

    obj.close()


@pytest.mark.parametrize("nitems", [0, 1, 2, 50])
@pytest.mark.parametrize("nsubscribers", [0, 1, 2, 70])
@pytest.mark.parametrize("thread", [True, False])
@pytest.mark.parametrize("close_register", [True, False])
@pytest.mark.asyncio
async def test_matrix(close_register, thread, nsubscribers, nitems):
    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    def register():
        for item in items:
            obj[key] = item
        if close_register:
            if key in obj:
                del obj[key]

    async def aregister():
        return register()

    obj = SubscribableDict()

    key = "item"
    items = tuple([f"{key}-{i+1}" for i in range(nitems)])

    # subscribe
    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe())
        tasks_subscribe.append(task)

    # register
    if thread:
        coro = to_thread(register)
    else:
        coro = aregister()
    task_register = asyncio.create_task(coro)

    await asyncio.gather(task_register)

    task_close = to_thread(obj.close)

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected
