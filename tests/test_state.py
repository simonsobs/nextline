import time

import pytest
from unittest.mock import Mock

from nextline.registry import PdbCIRegistry
from nextline.state import (
    Initialized,
    Running,
    Exited,
    Finished,
    Closed
)

##__________________________________________________________________||
SOURCE = """
import time
time.sleep(0.1)
""".strip()

##__________________________________________________________________||
@pytest.fixture(autouse=True)
def monkey_patch_trace(monkeypatch):
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_instance.pdb_ci_registry = Mock(spec=PdbCIRegistry)
    mocak_class = Mock(return_value=mock_instance)
    monkeypatch.setattr('nextline.state.Trace', mocak_class)
    yield mocak_class

@pytest.fixture()
def callback_exited():
    y = Mock()
    yield y

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_state_normal_flow(callback_exited):

    state = Initialized(SOURCE)
    assert isinstance(state, Initialized)
    assert "initialized" == state.registry.state_name

    state = state.run(exited=callback_exited)
    assert isinstance(state, Running)
    assert state.registry.state_name in ("running", "exited")

    state = await state.wait()
    assert isinstance(state, Finished)
    assert "finished" == state.registry.state_name

    state = await state.close()
    assert isinstance(state, Closed)
    assert "closed" == state.registry.state_name

@pytest.mark.asyncio
async def test_callback_exited(callback_exited):
    state = Initialized(SOURCE)
    state = state.run(exited=callback_exited)
    state = await state.wait()

    assert 1 == callback_exited.call_count
    state = callback_exited.call_args.args[0]
    assert isinstance(state, Exited)

##__________________________________________________________________||
