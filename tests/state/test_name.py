import asyncio
import itertools

import pytest

from nextline.state import Initialized
from nextline.utils import SubscribableDict


SOURCE = """
import time
time.sleep(0.001)
""".strip()


@pytest.fixture()
def registry():
    y = SubscribableDict()
    y["run_no_count"] = itertools.count().__next__
    y["statement"] = SOURCE
    yield y
    y.close()


@pytest.mark.asyncio
async def test_register_state_name(registry):
    async def subscribe():
        return [y async for y in registry.subscribe("state_name")]

    async def run():
        await asyncio.sleep(0)
        state = Initialized(registry=registry)
        state = state.run()
        state = await state.exited()
        state = await state.finish()
        state = state.close()
        registry.close()

    actual, _ = await asyncio.gather(subscribe(), run())

    expected = ["initialized", "running", "exited", "finished", "closed"]
    assert expected == actual


@pytest.mark.asyncio
async def test_register_state_name_reset(registry):
    async def subscribe():
        return [y async for y in registry.subscribe("state_name")]

    async def run():
        await asyncio.sleep(0)
        state = Initialized(registry=registry)
        state = state.reset()
        state = state.run()
        state = await state.exited()
        state = await state.finish()
        state = state.reset()
        state = state.run()
        state = await state.exited()
        state = await state.finish()
        state = state.close()
        registry.close()

    actual, _ = await asyncio.gather(subscribe(), run())

    expected = [
        "initialized",
        "initialized",
        "running",
        "exited",
        "finished",
        "initialized",
        "running",
        "exited",
        "finished",
        "closed",
    ]
    assert expected == actual
