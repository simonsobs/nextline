import asyncio
from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nextline.utils import PubSubItem, to_aiter


def test_init_without_asyncio_event_loop() -> None:
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    obj = PubSubItem[str]()
    assert obj


async def test_context() -> None:
    async with PubSubItem[str]() as obj:
        assert obj


async def test_close_multiple_times() -> None:
    async with PubSubItem[str]() as obj:
        await obj.aclose()
        await obj.aclose()


@given(...)
async def test_get(items: list[str]) -> None:
    async with PubSubItem[str]() as obj:
        with pytest.raises(LookupError):
            obj.latest()
        for item in items:
            await obj.publish(item)
            assert item == obj.latest()


@given(items=st.lists(st.text()), n_subscriptions=st.integers(0, 5))
async def test_subscribe(items: Sequence[str], n_subscriptions: int) -> None:
    items = tuple(items)
    expected = [items] * n_subscriptions

    async with PubSubItem[str]() as obj:

        async def receive() -> tuple[str, ...]:
            return tuple([i async for i in obj.subscribe()])

        async def send() -> None:
            async for i in to_aiter(items):
                await obj.publish(i)
            await obj.aclose()

        *results, _ = await asyncio.gather(
            *(receive() for _ in range(n_subscriptions)),
            send(),
        )
    assert results == expected
    assert obj.n_subscriptions == 0


@given(n_subscriptions=st.integers(0, 100))
async def test_n_subscriptions(n_subscriptions: int) -> None:
    async with PubSubItem[str]() as obj:

        async def receive() -> tuple[str, ...]:
            return tuple([i async for i in obj.subscribe()])

        task = asyncio.gather(*(receive() for _ in range(n_subscriptions)))
        await asyncio.sleep(0)
        assert obj.n_subscriptions == n_subscriptions
    await task
    assert obj.n_subscriptions == 0


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
) -> None:
    pre_items = tuple(pre_items)
    items = tuple(items)
    expected = [pre_items[-1:] + items if last else items] * n_subscriptions

    async with PubSubItem[int | str]() as obj:

        async def receive() -> tuple[int | str, ...]:
            return tuple([i async for i in obj.subscribe(last=last)])

        async def send() -> None:
            async for i in to_aiter(items):
                await obj.publish(i)
            await obj.aclose()

        for i in pre_items:
            await obj.publish(i)

        await asyncio.sleep(0.001)

        *results, _ = await asyncio.gather(
            *(receive() for _ in range(n_subscriptions)),
            send(),
        )
    assert results == expected


@given(...)
async def test_put_after_close(items: list[str], last_item: str) -> None:
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


@given(...)
async def test_subscribe_after_close(items: list[str]) -> None:
    async with PubSubItem[str]() as obj:
        for i in items:
            await obj.publish(i)

    await asyncio.sleep(0.001)

    async def receive() -> tuple[str, ...]:
        return tuple([i async for i in obj.subscribe()])

    results = await receive()
    assert results == ()  # empty
    assert obj.n_subscriptions == 0


@given(st.data())
async def test_break(data: st.DataObject) -> None:
    items = tuple(data.draw(st.lists(st.text(), min_size=1, unique=True)))
    idx = data.draw(st.integers(0, len(items) - 1))
    at = items[idx]

    expected = items[:idx]

    async with PubSubItem[str]() as obj:

        async def receive() -> tuple[str, ...]:
            ret = []
            assert obj.n_subscriptions == 0
            async for i in obj.subscribe():
                assert obj.n_subscriptions == 1
                if i == at:
                    break
                ret.append(i)
            await asyncio.sleep(0.001)
            assert obj.n_subscriptions == 0  # the queue is closed
            return tuple(ret)

        async def send() -> None:
            async for i in to_aiter(items):
                await obj.publish(i)
            await obj.aclose()

        results, _ = await asyncio.gather(receive(), send())
    assert results == expected


@given(st.data())
async def test_no_missing_or_duplicate(data: st.DataObject) -> None:
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

        async def receive() -> tuple[str, ...]:
            await event.wait()
            return tuple([i async for i in obj.subscribe()])

        async def send() -> None:
            async for i in to_aiter(pre_items):
                await obj.publish(i)
            event.set()
            async for i in to_aiter(post_items):
                await obj.publish(i)
            await obj.aclose()

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
