import asyncio
import io
from itertools import count
from weakref import WeakKeyDictionary

from typing import Any, Dict

import pytest

from nextline.io import IOSubscription
from nextline.utils import current_task_or_thread


@pytest.mark.asyncio
async def test_one(
    obj: IOSubscription,
    registry: Dict[str, Any],
    text_io: io.StringIO,
):
    messages = ("abc", "def", "\n", "ghi", "jkl", "\n")

    async def subscribe():
        return tuple([y async for y in obj.subscribe()])

    async def write(to_put: bool):
        trace_no = trace_no_counter()
        task_or_thread = current_task_or_thread()
        if to_put:
            registry["run_no_map"][task_or_thread] = run_no
            registry["trace_no_map"][task_or_thread] = trace_no
        await asyncio.sleep(0)
        for m in messages:
            obj.write(m)
            await asyncio.sleep(0)

    n = 2  # number of write(True)
    m = 1  # number of write(False)

    async def put():
        await asyncio.sleep(0.001)
        await asyncio.gather(
            write(True),
            write(True),
            write(False),
        )
        obj.close()

    run_no = 1
    trace_no_counter = count(1).__next__

    results, _ = await asyncio.gather(subscribe(), put())

    assert len("".join(messages) * (n + m)) == len(text_io.getvalue())

    assert len("".join(messages).split()) * n == len(results)
    expected = sorted("".join(messages).splitlines(True) * n)
    assert expected == sorted(r.text for r in results)


@pytest.fixture
def obj(registry: Dict[str, Any], text_io: io.StringIO):
    y = IOSubscription(text_io, registry)
    yield y


@pytest.fixture
def text_io():
    y = io.StringIO()
    yield y


@pytest.fixture
def registry():
    y = {}
    y["run_no_map"] = WeakKeyDictionary()
    y["trace_no_map"] = WeakKeyDictionary()
    yield y
