import time

import pytest
from unittest.mock import Mock

from nextline.registry import Registry, PdbCIRegistry
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

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()

##__________________________________________________________________||
@pytest.fixture(autouse=True)
def monkey_patch_trace(monkeypatch):
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_instance.pdb_ci_registry = Mock(spec=PdbCIRegistry)
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr('nextline.state.Trace', mock_class)
    yield mock_class

@pytest.fixture()
async def wrap_registry(monkeypatch):
    mock_class = Mock(side_effect=lambda : Mock(wraps=Registry()))
    monkeypatch.setattr('nextline.state.Registry', mock_class)
    yield

@pytest.fixture()
def callback_exited():
    y = Mock()
    yield y

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_state_transition(callback_exited):

    state = Initialized(SOURCE)
    assert isinstance(state, Initialized)

    state = state.run(exited=callback_exited)
    assert isinstance(state, Running)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = await state.close()
    assert isinstance(state, Closed)

    # The existed state is received by the callback
    assert 1 == callback_exited.call_count
    state, *_ = callback_exited.call_args.args
    assert isinstance(state, Exited)

@pytest.mark.asyncio
async def test_register_state_name(callback_exited, wrap_registry):

    state = Initialized(SOURCE)
    assert isinstance(state, Initialized)

    state = state.run(exited=callback_exited)
    assert isinstance(state, Running)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = await state.close()
    assert isinstance(state, Closed)

    expected = ['initialized', 'running', 'exited', 'finished', 'closed']
    actual = [a.args[0] for a in state.registry.register_state_name.call_args_list]
    assert expected == actual

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_exception(callback_exited):
    state = Initialized(SOURCE_RAISE)
    state = state.run(exited=callback_exited)

    state = await state.finish()
    assert isinstance(state, Finished)

    assert isinstance(state.exception(), Exception)
    assert ('foo', 'bar') == state.exception().args
    with pytest.raises(Exception):
        raise state.exception()

@pytest.mark.asyncio
async def test_exception_none(callback_exited):
    state = Initialized(SOURCE)
    state = state.run(exited=callback_exited)
    state = await state.finish()
    assert isinstance(state, Finished)

    assert state.exception() is None

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_result(callback_exited):
    state = Initialized(SOURCE)
    state = state.run(exited=callback_exited)

    state = await state.finish()
    assert isinstance(state, Finished)

    assert state.result() is None

@pytest.mark.asyncio
async def test_result_raise(callback_exited):
    state = Initialized(SOURCE_RAISE)
    state = state.run(exited=callback_exited)

    state = await state.finish()
    assert isinstance(state, Finished)

    with pytest.raises(Exception):
        state.result()

##__________________________________________________________________||
