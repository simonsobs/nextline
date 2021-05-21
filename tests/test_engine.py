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

    async def subscribe(engine, field, event):

        agen = engine.subscribe(field)
        first = True
        ret = []
        async for y in agen:
            ret.append(y)
            if first:
                event.set()
                first = False
        return ret

    def thread_register(engine, field, items, events):

        engine.add_field(field)
        assert engine.get(field) is None

        first = True
        for item in items:
            engine.register(field, item)
            assert engine.get(field) == item
            if not first:
                continue
            first = False
            for e in events:
                e.wait()

    async def async_register(engine, field, items, events):

        engine.add_field(field)
        assert engine.get(field) is None

        first = True
        for item in items:
            engine.register(field, item)
            assert engine.get(field) == item
            if not first:
                continue
            first = False
            if events:
                await asyncio.gather(*[e.wait() for e in events])

    engine = Engine()

    field = 'item'
    items = [f'{field}-{i+1}' for i in range(nitems)]

    events = []
    tasks_subscribe = []
    for i in range(nsubscribers):
        if thread:
            event = threading.Event()
        else:
            event = asyncio.Event()
        task = asyncio.create_task(subscribe(engine, field, event))
        events.append(event)
        tasks_subscribe.append(task)

    if thread:
        target = partial(thread_register, engine, field, items, events)
        task_register = asyncio.to_thread(target)
    else:
        task_register = asyncio.create_task(async_register(engine, field, items, events))

    await asyncio.gather(task_register)

    task_close = asyncio.create_task(engine.close())

    results = await asyncio.gather(*tasks_subscribe, task_close)
    expected = items
    actuals = results[:nsubscribers]
    for actual in actuals:
        assert actual == expected

##__________________________________________________________________||
