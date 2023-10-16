import asyncio
from typing import Sequence, Union

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nextline.utils import PubSubItem

from ..aiterable import aiterable


async def test_close():
    async with PubSubItem[str]() as obj:
        assert obj


async def test_close_multiple_times():
    async with PubSubItem[str]() as obj:
        await obj.close()
        await obj.close()


@given(items=st.lists(st.text()))
async def test_get(items: Sequence[str]):
    async with PubSubItem[str]() as obj:
        with pytest.raises(LookupError):
            obj.latest()
        for item in items:
            await obj.publish(item)
            assert item == obj.latest()


@given(items=st.lists(st.text()), n_subscriptions=st.integers(0, 5))
async def test_subscribe(items: Sequence[str], n_subscriptions: int):
    items = tuple(items)
    expected = [items] * n_subscriptions

    async with PubSubItem[str]() as obj:

        async def receive():
            return tuple([i async for i in obj.subscribe()])

        async def send():
            async for i in aiterable(items):
                await obj.publish(i)
            await obj.close()

        *results, _ = await asyncio.gather(
            *(receive() for _ in range(n_subscriptions)),
            send(),
        )
    assert results == expected
    assert obj.nsubscriptions == 0


@given(n_subscriptions=st.integers(0, 100))
async def test_nsubscriptions(n_subscriptions: int):
    async with PubSubItem[str]() as obj:

        async def receive():
            return tuple([i async for i in obj.subscribe()])

        task = asyncio.gather(*(receive() for _ in range(n_subscriptions)))
        await asyncio.sleep(0)
        assert obj.nsubscriptions == n_subscriptions
    await task
    assert obj.nsubscriptions == 0


@given(
    pre_items=st.lists(st.text()),
    items=st.lists(st.integers()),
    last=st.booleans(),
    n_subscriptions=st.integers(0, 20),
)
async def test_last(
    pre_items: Sequence[str],
    items: Sequence[int],
    last: bool,
    n_subscriptions: int,
):
    pre_items = tuple(pre_items)
    items = tuple(items)
    expected = [pre_items[-1:] + items if last else items] * n_subscriptions

    async with PubSubItem[Union[int, str]]() as obj:

        async def receive():
            return tuple([i async for i in obj.subscribe(last=last)])

        async def send():
            async for i in aiterable(items):
                await obj.publish(i)
            await obj.close()

        for i in pre_items:
            await obj.publish(i)

        await asyncio.sleep(0.001)

        *results, _ = await asyncio.gather(
            *(receive() for _ in range(n_subscriptions)),
            send(),
        )
    assert results == expected


@given(items=st.lists(st.text()), last_item=st.text())
async def test_put_after_close(items: Sequence[str], last_item: str):
    async with PubSubItem[str]() as obj:
        for i in items:
            await obj.publish(i)
    with pytest.raises(RuntimeError):
        await obj.publish(last_item)
    if items:
        assert obj.latest() == items[-1]  # the last item is not replaced
    else:
        with pytest.raises(LookupError):
            obj.latest()


@given(items=st.lists(st.text()))
async def test_subscribe_after_close(items: Sequence[str]):
    async with PubSubItem[str]() as obj:
        for i in items:
            await obj.publish(i)

    await asyncio.sleep(0.001)

    async def receive():
        return tuple([i async for i in obj.subscribe()])

    results = await receive()
    assert results == ()  # empty
    assert obj.nsubscriptions == 0


@given(st.data())
async def test_break(data: st.DataObject):
    items = tuple(data.draw(st.lists(st.text(), min_size=1, unique=True)))
    idx = data.draw(st.integers(0, len(items) - 1))
    at = items[idx]

    expected = items[:idx]

    async with PubSubItem[str]() as obj:

        async def receive():
            ret = []
            assert obj.nsubscriptions == 0
            async for i in obj.subscribe():
                assert obj.nsubscriptions == 1
                if i == at:
                    break
                ret.append(i)
            await asyncio.sleep(0.001)
            assert obj.nsubscriptions == 0  # the queue is closed
            return tuple(ret)

        async def send():
            async for i in aiterable(items):
                await obj.publish(i)
            await obj.close()

        results, _ = await asyncio.gather(receive(), send())
    assert results == expected


@given(st.data())
async def test_no_missing_or_duplicate(data: st.DataObject):
    '''Assert that the issue is resolved
    https://github.com/simonsobs/nextline/issues/2

    '''

    n_subscriptions = data.draw(st.integers(0, 20))
    items = tuple(data.draw(st.lists(st.text(), unique=True)))

    split = data.draw(st.integers(0, len(items)))

    pre_items = items[:split]
    post_items = items[split:]

    event = asyncio.Event()

    async with PubSubItem[str]() as obj:

        async def receive():
            await event.wait()
            return tuple([i async for i in obj.subscribe()])

        async def send():
            async for i in aiterable(pre_items):
                await obj.publish(i)
            event.set()
            async for i in aiterable(post_items):
                await obj.publish(i)
            await obj.close()

        *results, _ = await asyncio.gather(
            *(receive() for _ in range(n_subscriptions)),
            send(),
        )

    for actual in results:
        if not actual:  # can be empty
            continue
        expected = items[items.index(actual[0]) :]  # no missing or duplicate
        assert actual == expected
        # print(actual)
        # print(actual[0] in pre_items)
