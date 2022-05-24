import asyncio

import pytest

from nextline.utils import SubscribableDict, to_thread

from .aiterable import aiterable


@pytest.mark.asyncio
async def test_end():
    obj: SubscribableDict[str, str] = SubscribableDict()
    key = "A"

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def end():
        await asyncio.sleep(0.001)
        obj.end(key)

    results = await asyncio.gather(subscribe(), end())
    print(results)


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
