import asyncio
from string import ascii_lowercase, ascii_uppercase
import time

import pytest

from nextline.utils import PubSub


@pytest.fixture
async def obj():
    async with PubSub() as y:
        yield y


async def test_end(obj: PubSub[str, str]):
    key = "A"

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        await obj.end(key)

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == ()


async def test_end_without_subscription(obj: PubSub[str, str]):
    key = "A"
    await obj.end(key)


async def test_close(obj: PubSub[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        for item in items:
            await obj.publish(key, item)
        assert obj.latest(key) == items[-1]
        await obj.close()  # ends the subscription
        with pytest.raises(LookupError):
            obj.latest(key)

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.parametrize("last", [True, False])
async def test_last(obj: PubSub[str, str], last: bool):
    key = "A"
    n_pre_items = 3
    n_items = 5
    pre_items = tuple(reversed(ascii_lowercase[-n_pre_items:]))
    items = tuple(ascii_lowercase[:n_items])
    expected = pre_items[-1:] + items if last else items

    for item in pre_items:
        await obj.publish(key, item)

    await asyncio.sleep(0.001)

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key, last=last)])

    async def put():
        await asyncio.sleep(0.001)
        for item in items:
            await obj.publish(key, item)
        await obj.end(key)

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == expected


@pytest.mark.parametrize("n_keys", [0, 1, 3])
@pytest.mark.parametrize("n_items", [0, 1, 2, 30])
@pytest.mark.parametrize("n_subscribers", [0, 1, 2, 50])
async def test_matrix(
    obj: PubSub[str, str],
    n_keys: int,
    n_items: int,
    n_subscribers: int,
):
    keys = ascii_uppercase[:n_keys]
    items = {k: tuple(f"{k}-{i+1}" for i in range(n_items)) for k in keys}

    async def subscribe(key):
        return tuple([y async for y in obj.subscribe(key)])

    async def put(key):
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
