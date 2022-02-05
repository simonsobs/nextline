import pytest

from nextline.state import (
    Initialized,
    Running,
    Exited,
    Finished,
    Closed,
)

SOURCE = """
import time
time.sleep(0.001)
""".strip()


@pytest.mark.asyncio
async def test_transition():

    state = Initialized(SOURCE)
    assert isinstance(state, Initialized)

    state = state.run()
    assert isinstance(state, Running)

    state = await state.exited()
    assert isinstance(state, Exited)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = await state.close()
    assert isinstance(state, Closed)
