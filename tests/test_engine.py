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
@pytest.mark.asyncio
async def test_one(thread, nsubscribers, nitems):

    async def subscribe(engine, register_name):
        ret = []
        async for y in engine.subscribe(register_name):
            ret.append(y)
        return ret

    def register(engine, register_name, items):
        engine.open_register(register_name)
        assert engine.get(register_name) is None
        for item in items:
            engine.register(register_name, item)
            assert engine.get(register_name) == item

    async def aregister(engine, register_name, items):
        return register(engine, register_name, items)

    engine = Engine()

    register_name = 'item'
    items = [f'{register_name}-{i+1}' for i in range(nitems)]

    # subscribe
    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe(engine, register_name))
        tasks_subscribe.append(task)

    # register
    if thread:
        coro = asyncio.to_thread(register, engine, register_name, items)
    else:
        coro = aregister(engine, register_name, items)
    task_register = asyncio.create_task(coro)

    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected

##__________________________________________________________________||
