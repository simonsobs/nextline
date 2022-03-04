import itertools

import pytest

from nextline.state import (
    Initialized,
    Running,
    Exited,
    Finished,
    Closed,
)
from nextline.utils import SubscribableDict

SOURCE = """
import time
time.sleep(0.001)
""".strip()


@pytest.fixture()
def registry():
    y = SubscribableDict()
    y["run_no_count"] = itertools.count().__next__
    yield y
    y.close()


@pytest.mark.asyncio
async def test_transition(registry):
    registry["statement"] = SOURCE

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
