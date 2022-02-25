import asyncio

import pytest

from nextline.utils import Registry, to_thread

from .aiterable import aiterable


@pytest.mark.asyncio
async def test_simple_usage():
    obj = Registry()

    key = "key_one"
    items = ["item_one", "item_two", "item_three"]

    async def subscribe():
        return [y async for y in obj.subscribe(key)]

    async def register():
        obj.open_register(key)
        async for i in aiterable(items):
            obj.register(key, i)
            assert i == obj.get(key)
        obj.close_register(key)

    results = await asyncio.gather(subscribe(), register())
    assert items == results[0]

    obj.close()


@pytest.mark.asyncio
async def test_get_default():
    obj = Registry()

    key = "no_such_key"
    assert obj.get(key) is None

    key = "no_such_key"
    assert 123 == obj.get(key, 123)

    obj.close()


##__________________________________________________________________||
nitems = [0, 1, 2, 50]
nsubscribers = [0, 1, 2, 70]


@pytest.mark.parametrize("nitems", nitems)
@pytest.mark.parametrize("nsubscribers", nsubscribers)
@pytest.mark.parametrize("thread", [True, False])
@pytest.mark.parametrize("close_register", [True, False])
@pytest.mark.asyncio
async def test_one(close_register, thread, nsubscribers, nitems):
    async def subscribe(registry, register_key):
        ret = []
        async for y in registry.subscribe(register_key):
            ret.append(y)
        return ret

    def register(registry, register_key, items):
        registry.open_register(register_key)
        assert registry.get(register_key) is None
        for item in items:
            registry.register(register_key, item)
            assert registry.get(register_key) == item
        if close_register:
            registry.close_register(register_key)

    async def aregister(registry, register_key, items):
        return register(registry, register_key, items)

    registry = Registry()

    register_key = "item"
    items = [f"{register_key}-{i+1}" for i in range(nitems)]

    # subscribe
    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe(registry, register_key))
        tasks_subscribe.append(task)

    # register
    if thread:
        coro = to_thread(register, registry, register_key, items)
    else:
        coro = aregister(registry, register_key, items)
    task_register = asyncio.create_task(coro)

    await asyncio.gather(task_register)

    task_close = to_thread(registry.close)

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected
