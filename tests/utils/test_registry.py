import asyncio

import pytest

from nextline.utils import SubscribableDict, to_thread

from .aiterable import aiterable


@pytest.mark.asyncio
async def test_one():
    obj = SubscribableDict()

    key = "key_one"
    items = ["item_one", "item_two", "item_three"]

    async def subscribe():
        return [y async for y in obj.subscribe(key)]

    async def send():
        async for i in aiterable(items):
            obj[key] = i
            assert i == obj[key]
        assert 1 == len(obj)
        assert [key] == list(obj)
        del obj[key]
        assert 0 == len(obj)
        assert [] == list(obj)

    results = await asyncio.gather(subscribe(), subscribe(), send())
    assert items == results[0]
    assert items == results[1]

    obj.close()


def test_key_error():
    obj = SubscribableDict()

    key = "no_such_key"
    with pytest.raises(KeyError):
        obj[key]

    assert 0 == len(obj)
    assert not obj

    obj.close()


def test_get():
    obj = SubscribableDict()

    key = "no_such_key"
    assert obj.get(key) is None

    key = "no_such_key"
    assert 123 == obj.get(key, 123)

    assert 0 == len(obj)
    assert not obj

    obj.close()


nitems = [0, 1, 2, 50]
nsubscribers = [0, 1, 2, 70]


@pytest.mark.parametrize("nitems", nitems)
@pytest.mark.parametrize("nsubscribers", nsubscribers)
@pytest.mark.parametrize("thread", [True, False])
@pytest.mark.parametrize("close_register", [True, False])
@pytest.mark.asyncio
async def test_matrix(close_register, thread, nsubscribers, nitems):
    async def subscribe():
        return [y async for y in obj.subscribe(key)]

    def register():
        for item in items:
            obj[key] = item
            assert obj[key] == item
        if close_register:
            del obj[key]

    async def aregister():
        return register()

    obj = SubscribableDict()

    key = "item"
    items = [f"{key}-{i+1}" for i in range(nitems)]

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
