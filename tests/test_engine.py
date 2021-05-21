import asyncio
from collections import deque

import pytest
from unittest.mock import Mock, sentinel

from nextline.registry import Engine

##__________________________________________________________________||
@pytest.mark.parametrize('nitems', [0, 1, 2, 5])
@pytest.mark.asyncio
async def test_one(nitems):

    async def subscribe(engine, field, event):
        # print(' '*50, 1)
        agen = engine.subscribe(field)
        ret = []
        async for y in agen:
            ret.append(y)
            event.set()
        return ret

    async def register(engine, field, items, event):
        # print(' '*50, 2)
        items = list(items) # not to modify the original

        engine.add_field(field)
        assert engine.get(field) is None

        for i, item in enumerate(items):
            engine.register(field, item)
            assert engine.get(field) == item
            if i == 0:
                await event.wait()

    event = asyncio.Event()
    engine = Engine()

    field = 'item'
    items = [f'{field}-{i+1}' for i in range(nitems)]


    task_subscribe = asyncio.create_task(subscribe(engine, field, event))

    task_register = asyncio.create_task(register(engine, field, items, event))
    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(task_subscribe, task_close)
    actual, *_ = results
    assert actual == items

##__________________________________________________________________||
