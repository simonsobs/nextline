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


@pytest.mark.asyncio
async def test_transition():
    registry = Registry()
    registry.open_register("statement")
    registry.open_register("state_name")
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
