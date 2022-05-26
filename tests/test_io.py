import asyncio
import io
from itertools import count
from weakref import WeakKeyDictionary

from typing import Any

import pytest
from unittest.mock import Mock, call

from nextline.io import IOSubscription, IOPeekWrite
from nextline.utils import SubscribableDict, current_task_or_thread


def test_peek():
    wrap = io.StringIO()
    src = Mock(spec=io.StringIO, wraps=wrap)
    callback = Mock()
    obj = IOPeekWrite(src, callback)
    assert obj.write("foo")
    assert obj.write("bar")
    assert obj.write("\n")
    obj.flush()
    assert [
        call.write("foo"),
        call.write("bar"),
        call.write("\n"),
        call.flush(),
    ] == src.method_calls
    assert [call("foo"), call("bar"), call("\n")] == callback.call_args_list
    assert "foobar\n" == wrap.getvalue()


@pytest.mark.asyncio
async def test_one(
    registry: SubscribableDict[str, Any],
    text_io: io.StringIO,
):
    obj = IOSubscription(registry)
    out = obj.create_out(text_io)

    messages = ("abc", "def", "\n", "ghi", "jkl", "\n")

    async def subscribe():
        return tuple([y async for y in registry.subscribe("stdout")])

    async def write(to_put: bool):
        trace_no = trace_no_counter()
        task_or_thread = current_task_or_thread()
        if to_put:
            registry["run_no_map"][task_or_thread] = run_no
            registry["trace_no_map"][task_or_thread] = trace_no
        await asyncio.sleep(0)
        for m in messages:
            out.write(m)
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
        registry.close()

    run_no = 1
    trace_no_counter = count(1).__next__

    results, _ = await asyncio.gather(subscribe(), put())

    assert len("".join(messages) * (n + m)) == len(text_io.getvalue())

    assert len("".join(messages).split()) * n == len(results)
    expected = sorted("".join(messages).splitlines(True) * n)
    assert expected == sorted(r.text for r in results)


@pytest.fixture
def text_io():
    y = io.StringIO()
    yield y


@pytest.fixture
def registry():
    y = SubscribableDict()
    y["run_no_map"] = WeakKeyDictionary()
    y["trace_no_map"] = WeakKeyDictionary()
    yield y
