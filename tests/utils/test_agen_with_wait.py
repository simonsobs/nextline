import asyncio
from random import randint, random

import pytest

from nextline.utils import agen_with_wait


async def test_one() -> None:
    async def agen():
        for i in range(3):
            yield i
            await asyncio.sleep(0.001)

    async def afunc():
        delay = random() * 0.001
        await asyncio.sleep(delay)

    all = set[asyncio.Task]()
    done = list[asyncio.Task]()

    obj = agen_with_wait(agen())
    async for _ in obj:
        tasks = {asyncio.create_task(afunc()) for _ in range(randint(0, 5))}
        all |= tasks
        done_, pending = await obj.asend(tasks)
        done.extend(done_)  # type: ignore

    await asyncio.gather(*pending)
    assert len(all) == len(done) + len(pending)
    assert all == set(done) | set(pending)


async def test_raise():
    async def agen():
        yield 0
        await asyncio.sleep(0.1)
        assert False  # The line shouldn't be reached

    async def afunc():
        await asyncio.sleep(0)
        raise Exception("foo", "bar")

    obj = agen_with_wait(agen())
    with pytest.raises(Exception) as exc:
        async for _ in obj:
            tasks = {asyncio.create_task(afunc())}
            _, pending = await obj.asend(tasks)

    assert ("foo", "bar") == exc.value.args


async def test_without_send():
    async def agen():
        for i in range(3):
            yield i
            await asyncio.sleep(0)

    items = []
    async for i in agen_with_wait(agen()):
        # print(i)
        items.append(i)

    assert [0, 1, 2] == items
