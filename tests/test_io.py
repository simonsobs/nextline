import asyncio
import io
from itertools import count
from weakref import WeakKeyDictionary

from typing import Any

import pytest

from nextline.io import IOSubscription
from nextline.utils import (
    SubscribableDict,
    ThreadTaskIdComposer,
    current_task_or_thread,
)


@pytest.mark.asyncio
async def test_one(
    obj: IOSubscription,
    registry: SubscribableDict[str, Any],
    text_io: io.StringIO,
):
    async def subscribe():
        return [y async for y in obj.subscribe()]

    async def write():
        trace_no = trace_no_counter()
        task_or_thread = current_task_or_thread()
        registry["trace_id_factory"]()
        registry["run_no_map"][task_or_thread] = run_no
        registry["trace_no_map"][task_or_thread] = trace_no
        await asyncio.sleep(0)
        # print("abcdef", file=obj)
        obj.write("abc")
        await asyncio.sleep(0)
        obj.write("def")
        await asyncio.sleep(0)
        obj.write("\n")
        await asyncio.sleep(0)

    run_no = 1
    trace_no_counter = count(1).__next__

    t = asyncio.create_task(subscribe())

    await asyncio.sleep(0)

    await asyncio.gather(
        asyncio.create_task(write()),
        asyncio.create_task(write()),
    )

    assert len("abcdef\n" * 2) == len(text_io.getvalue())

    await asyncio.sleep(0)

    obj.close()

    results = await t
    # print(results)
    assert 2 == len(results)
    assert ["abcdef\n"] * 2 == [r.text for r in results]


@pytest.fixture
def obj(registry: SubscribableDict[str, Any], text_io: io.StringIO):
    y = IOSubscription(text_io, registry)
    yield y


@pytest.fixture
def text_io():
    y = io.StringIO()
    yield y


@pytest.fixture
def registry():
    y = SubscribableDict[str, Any]()
    y["trace_id_factory"] = ThreadTaskIdComposer()
    y["run_no_map"] = WeakKeyDictionary()
    y["trace_no_map"] = WeakKeyDictionary()
    yield y
