import sys
import threading
import asyncio
from functools import partial
from collections import deque

import pytest

from nextline.registry import Engine

##__________________________________________________________________||
nitems = [0, 1, 2, 5]
nsubscribers = [0, 1, 2, 7]

@pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread() ")
@pytest.mark.parametrize('nitems', nitems)
@pytest.mark.parametrize('nsubscribers', nsubscribers)
@pytest.mark.parametrize('thread', [True, False])
@pytest.mark.asyncio
async def test_one(thread, nsubscribers, nitems):

    async def subscribe(engine, field):

        agen = engine.subscribe(field)
        ret = []
        async for y in agen:
            ret.append(y)
        return ret

    def thread_register(engine, field, items):

        engine.add_field(field)
        assert engine.get(field) is None

        for item in items:
            engine.register(field, item)
            assert engine.get(field) == item

    async def async_register(engine, field, items):

        engine.add_field(field)
        assert engine.get(field) is None

        for item in items:
            engine.register(field, item)
            assert engine.get(field) == item

    engine = Engine()

    field = 'item'
    items = [f'{field}-{i+1}' for i in range(nitems)]

    tasks_subscribe = []
    for i in range(nsubscribers):
        task = asyncio.create_task(subscribe(engine, field))
        tasks_subscribe.append(task)

    if thread:
        target = partial(thread_register, engine, field, items)
        task_register = asyncio.to_thread(target)
    else:
        task_register = asyncio.create_task(async_register(engine, field, items))

    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected

##__________________________________________________________________||
