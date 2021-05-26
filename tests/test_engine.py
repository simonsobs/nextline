import sys
import asyncio

import pytest

from nextline.registry import Engine

##__________________________________________________________________||
nitems = [0, 1, 2, 50]
nsubscribers = [0, 1, 2, 70]

@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread() ")
@pytest.mark.parametrize('nitems', nitems)
@pytest.mark.parametrize('nsubscribers', nsubscribers)
@pytest.mark.parametrize('thread', [True, False])
@pytest.mark.parametrize('close_register', [True, False])
@pytest.mark.asyncio
async def test_one(close_register, thread, nsubscribers, nitems):

    async def subscribe(engine, register_key):
        ret = []
        async for y in engine.subscribe(register_key):
            ret.append(y)
        return ret

    def register(engine, register_key, items):
        engine.open_register(register_key)
        assert engine.get(register_key) is None
        for item in items:
            engine.register(register_key, item)
            assert engine.get(register_key) == item
        if close_register:
            engine.close_register(register_key)

    async def aregister(engine, register_key, items):
        return register(engine, register_key, items)

    engine = Engine()

    register_key = 'item'
    items = [f'{register_key}-{i+1}' for i in range(nitems)]

    # subscribe
    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe(engine, register_key))
        tasks_subscribe.append(task)

    # register
    if thread:
        coro = asyncio.to_thread(register, engine, register_key, items)
    else:
        coro = aregister(engine, register_key, items)
    task_register = asyncio.create_task(coro)

    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected

##__________________________________________________________________||
nitems = [0, 1, 2, 10]
nsubscribers = [0, 1, 2, 70]

@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread() ")
@pytest.mark.parametrize('nitems', nitems)
@pytest.mark.parametrize('nsubscribers', nsubscribers)
@pytest.mark.parametrize('thread', [True, False])
@pytest.mark.parametrize('close_register', [True, False])
@pytest.mark.asyncio
async def test_list(close_register, thread, nsubscribers, nitems):

    async def subscribe(engine, register_key):
        ret = []
        async for y in engine.subscribe(register_key):
            ret.append(y)
        return ret

    def register(engine, register_key, items):
        engine.open_register_list(register_key)
        assert engine.get(register_key) == []
        for i, item in enumerate(items):
            engine.register_list_item(register_key, item)
            assert engine.get(register_key) == items[:i+1]
        for i, item in enumerate(items):
            engine.deregister_list_item(register_key, item)
            assert engine.get(register_key) == items[i+1:]
        if close_register:
            engine.close_register(register_key)

    async def aregister(engine, register_key, items):
        return register(engine, register_key, items)

    engine = Engine()

    register_key = 'item'
    items = [f'{register_key}-{i+1}' for i in range(nitems)]

    # subscribe
    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe(engine, register_key))
        tasks_subscribe.append(task)

    # register
    if thread:
        coro = asyncio.to_thread(register, engine, register_key, items)
    else:
        coro = aregister(engine, register_key, items)
    task_register = asyncio.create_task(coro)

    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = [items[:i+1] for i in range(len(items))]
    expected.extend([items[i+1:] for i in range(len(items))])
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected

##__________________________________________________________________||
