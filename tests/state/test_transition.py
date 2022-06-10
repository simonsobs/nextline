import pytest

from nextline.state import Initialized, Running, Finished, Closed
from nextline.process.run import RunArg


@pytest.fixture
def context() -> RunArg:
    y = RunArg()
    return y


@pytest.mark.asyncio
async def test_transition(context: RunArg):

    state = Initialized(context=context)
    assert isinstance(state, Initialized)

    state = state.run()
    assert isinstance(state, Running)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = state.close()
    assert isinstance(state, Closed)


@pytest.fixture(autouse=True)
def monkey_patch_run(monkey_patch_run):
    yield monkey_patch_run
