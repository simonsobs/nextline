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

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_state_transition():

    state = Initialized(SOURCE)
    assert isinstance(state, Initialized)

    state = state.run()
    assert isinstance(state, Running)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = await state.close()
    assert isinstance(state, Closed)

@pytest.mark.asyncio
async def test_exited_callback():

    callback = Mock()

    state = Initialized(SOURCE, exited=callback)
    assert isinstance(state, Initialized)

    state = state.run()
    assert isinstance(state, Running)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = await state.close()
    assert isinstance(state, Closed)

    # The existed state is received by the callback
    assert 1 == callback.call_count
    state, *_ = callback.call_args.args
    assert isinstance(state, Exited)

@pytest.mark.asyncio
async def test_state_transition_once():

    callback = Mock()

    initialized = Initialized(SOURCE, exited=callback)
    assert isinstance(initialized, Initialized)

    running = initialized.run()
    assert isinstance(running, Running)

    assert running is initialized.run() # the same object

    finished = await running.finish()
    assert isinstance(finished, Finished)

    assert finished is await running.finish() # the same object

    closed = await finished.close()
    assert isinstance(closed, Closed)

    assert closed is await finished.close() # the same object

    # The existed state is received by the callback
    assert 1 == callback.call_count
    exited, *_ = callback.call_args.args
    assert isinstance(exited, Exited)

    assert finished is await exited.finish() # the same object

@pytest.mark.asyncio
async def test_exited_callback_raise():

    callback = Mock(side_effect=Exception('ntYpOsermaRb'))

    state = Initialized(SOURCE, exited=callback)
    assert isinstance(state, Initialized)

    with pytest.warns(UserWarning) as record:
        state = state.run()
        assert isinstance(state, Running)

        state = await state.finish()
        assert isinstance(state, Finished)

    assert "ntYpOsermaRb" in (record[0].message.args[0])

    state = await state.close()
    assert isinstance(state, Closed)

@pytest.mark.asyncio
async def test_register_state_name(wrap_registry):

    state = Initialized(SOURCE)
    assert isinstance(state, Initialized)

    state = state.run()
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
async def test_exception():
    state = Initialized(SOURCE_RAISE)
    state = state.run()

    state = await state.finish()
    assert isinstance(state, Finished)

    assert isinstance(state.exception(), Exception)
    assert ('foo', 'bar') == state.exception().args
    with pytest.raises(Exception):
        raise state.exception()

@pytest.mark.asyncio
async def test_exception_none():
    state = Initialized(SOURCE)
    state = state.run()
    state = await state.finish()
    assert isinstance(state, Finished)

    assert state.exception() is None

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_result():
    state = Initialized(SOURCE)
    state = state.run()

    state = await state.finish()
    assert isinstance(state, Finished)

    assert state.result() is None

@pytest.mark.asyncio
async def test_result_raise():
    state = Initialized(SOURCE_RAISE)
    state = state.run()

    state = await state.finish()
    assert isinstance(state, Finished)

    with pytest.raises(Exception):
        state.result()

##__________________________________________________________________||
