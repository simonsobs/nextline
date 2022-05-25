import asyncio
from string import ascii_lowercase, ascii_uppercase
import time

import pytest

from nextline.utils import SubscribableDict, to_thread


@pytest.fixture
def obj():
    y = SubscribableDict()
    yield y
    y.close()


@pytest.mark.asyncio
async def test_end(obj: SubscribableDict[str, str]):
    key = "A"

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        obj.end(key)

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == ()


@pytest.mark.asyncio
async def test_end_without_subscription(obj: SubscribableDict[str, str]):
    key = "A"
    obj.end(key)


@pytest.mark.asyncio
async def test_close(obj: SubscribableDict[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        for item in items:
            obj[key] = item
        obj.close()  # ends the subscription
        assert obj[key] == items[-1]  # the last item is still there

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.asyncio
async def test_clear(obj: SubscribableDict[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        obj.clear()  # doesn't end the subscription as no item hasn't been put
        for item in items:
            obj[key] = item
        obj.clear()  # ends the subscription
        assert key not in obj  # the item is deleted

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.asyncio
async def test_del(obj: SubscribableDict[str, str]):
    key = "A"
    n_items = 5
    items = tuple(ascii_lowercase[:n_items])

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        with pytest.raises(KeyError):
            del obj[key]  # this doesn't end the subscription
        for item in items:
            obj[key] = item
        del obj[key]  # this ends the subscription
        assert key not in obj

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == items


@pytest.mark.asyncio
@pytest.mark.parametrize("last", [True, False])
async def test_last(obj: SubscribableDict[str, str], last: bool):
    key = "A"
    n_pre_items = 3
    n_items = 5
    pre_items = tuple(reversed(ascii_lowercase[-n_pre_items:]))
    items = tuple(ascii_lowercase[:n_items])
    expected = pre_items[-1:] + items if last else items

    for item in pre_items:
        obj[key] = item

    await asyncio.sleep(0.001)

    async def subscribe():
        return tuple([y async for y in obj.subscribe(key, last=last)])

    async def put():
        await asyncio.sleep(0.001)
        for item in items:
            obj[key] = item
        del obj[key]

    result, _ = await asyncio.gather(subscribe(), put())
    assert result == expected


@pytest.mark.asyncio
async def test_init():
    n_keys = 2
    keys = ascii_uppercase[:n_keys]
    data = {k: f"{k}-a" for k in keys}
    obj: SubscribableDict[str, str] = SubscribableDict(data)
    expected = [(data[k],) for k in keys]

    async def subscribe(key):
        return tuple([y async for y in obj.subscribe(key)])

    async def put():
        await asyncio.sleep(0.001)
        for key in keys:
            del obj[key]

    *results, _ = await asyncio.gather(*(subscribe(k) for k in keys), put())
    assert results == expected


@pytest.mark.parametrize("n_keys", [0, 1, 3])
@pytest.mark.parametrize("n_items", [0, 1, 2, 30])
@pytest.mark.parametrize("n_subscribers", [0, 1, 2, 50])
@pytest.mark.asyncio
async def test_matrix(
    obj: SubscribableDict[str, str],
    n_keys: int,
    n_items: int,
    n_subscribers: int,
):
    keys = ascii_uppercase[:n_keys]
    items = {k: tuple(f"{k}-{i+1}" for i in range(n_items)) for k in keys}

    async def subscribe(key):
        return tuple([y async for y in obj.subscribe(key)])

    def put(key):
        time.sleep(0.01)
        for item in items[key]:
            obj[key] = item
        obj.end(key)

    results = await asyncio.gather(
        *(subscribe(k) for k in keys for _ in range(n_subscribers)),
        *(to_thread(put, k) for k in keys),
    )
    actual = results[: n_subscribers * n_keys]
    expected = [items[k] for k in keys for _ in range(n_subscribers)]
    assert actual == expected
