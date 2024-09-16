import asyncio
import time
from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nextline.utils import PubSub


async def test_end() -> None:
    key = 'foo'
    async with PubSub[str, str]() as obj:

        async def subscribe() -> tuple[str, ...]:
            return tuple([y async for y in obj.subscribe(key)])

        async def put() -> None:
            await asyncio.sleep(0.001)
            await obj.end(key)

        result, _ = await asyncio.gather(subscribe(), put())
    assert result == ()


async def test_end_without_subscription() -> None:
    key = 'foo'
    async with PubSub[str, str]() as obj:
        await obj.end(key)


@given(items=st.lists(st.text()))
async def test_close(items: Sequence[str]) -> None:
    items = tuple(items)
    key = 'foo'

    async with PubSub[str, str]() as obj:

        async def subscribe() -> tuple[str, ...]:
            return tuple([y async for y in obj.subscribe(key)])

        async def put() -> None:
            await asyncio.sleep(0.001)
            for item in items:
                await obj.publish(key, item)
            if items:
                assert obj.latest(key) == items[-1]
            await obj.close()  # ends the subscription
            with pytest.raises(LookupError):
                obj.latest(key)

        result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@given(
    pre_items=st.lists(st.text()),
    items=st.lists(st.text()),
    last=st.booleans(),
)
async def test_last(
    pre_items: Sequence[str],
    items: Sequence[str],
    last: bool,
) -> None:
    key = 'foo'
    pre_items = tuple(pre_items)
    items = tuple(items)
    expected = pre_items[-1:] + items if last else items

    async with PubSub[str, str]() as obj:
        for item in pre_items:
            await obj.publish(key, item)

        await asyncio.sleep(0.001)

        async def subscribe() -> tuple[str, ...]:
            return tuple([y async for y in obj.subscribe(key, last=last)])

        async def put() -> None:
            await asyncio.sleep(0.001)
            for item in items:
                await obj.publish(key, item)
            await obj.end(key)

        result, _ = await asyncio.gather(subscribe(), put())
    assert result == expected


@given(
    keys=st.lists(st.text(), max_size=3, unique=True),
    n_items=st.integers(0, 30),
    n_subscribers=st.integers(0, 20),
)
async def test_matrix(
    keys: Sequence[str],
    n_items: int,
    n_subscribers: int,
) -> None:
    keys = tuple(keys)
    n_keys = len(keys)
    items = {k: tuple(f"{k}-{i+1}" for i in range(n_items)) for k in keys}

    async with PubSub[str, str]() as obj:

        async def subscribe(key: str) -> tuple[str, ...]:
            return tuple([y async for y in obj.subscribe(key)])

        async def put(key: str) -> None:
            time.sleep(0.01)
            for item in items[key]:
                await obj.publish(key, item)
            await obj.end(key)

        results = await asyncio.gather(
            *(subscribe(k) for k in keys for _ in range(n_subscribers)),
            *(put(k) for k in keys),
        )
        actual = results[: n_subscribers * n_keys]
        expected = [items[k] for k in keys for _ in range(n_subscribers)]
    assert actual == expected
