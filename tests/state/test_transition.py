import itertools

import pytest

from nextline.state import (
    Initialized,
    Running,
    Exited,
    Finished,
    Closed,
)
from nextline.utils import Registry

SOURCE = """
import time
time.sleep(0.001)
""".strip()


@pytest.fixture()
async def registry():
    y = Registry()
    y.open_register("statement")
    y.open_register("state_name")
    y.open_register("run_no")
    y.open_register("run_no_count")
    y.register("run_no_count", itertools.count().__next__)
    yield y
    await y.close()


@pytest.mark.asyncio
async def test_transition(registry):
    registry.register("statement", SOURCE)

    state = Initialized(registry=registry)
    assert isinstance(state, Initialized)

    state = state.run()
    assert isinstance(state, Running)

    state = await state.exited()
    assert isinstance(state, Exited)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = state.close()
    assert isinstance(state, Closed)
