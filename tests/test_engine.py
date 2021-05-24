import sys
import threading
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

    async def subscribe(engine, field):
        ret = []
        async for y in engine.subscribe(field):
            ret.append(y)
        return ret

    def register(engine, field, items):
        engine.add_field(field)
        assert engine.get(field) is None
        for item in items:
            engine.register(field, item)
            assert engine.get(field) == item

    async def aregister(engine, field, items):
        return register(engine, field, items)

    engine = Engine()

    field = 'item'
    items = [f'{field}-{i+1}' for i in range(nitems)]

    # subscribe
    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe(engine, field))
        tasks_subscribe.append(task)

    # register
    if thread:
        coro = asyncio.to_thread(register, engine, field, items)
    else:
        coro = aregister(engine, field, items)
    task_register = asyncio.create_task(coro)

    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected

##__________________________________________________________________||
