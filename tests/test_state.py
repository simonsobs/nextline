import time
from abc import ABC, abstractmethod

import pytest
from unittest.mock import Mock

from nextline.registry import Registry, PdbCIRegistry
from nextline.state import (
    Initialized,
    Running,
    Exited,
    Finished,
    Closed,
    StateObsoleteError,
    StateMethodError
)

##__________________________________________________________________||
SOURCE_ONE = """
import time
time.sleep(0.1)
""".strip()

SOURCE_TWO = """
x = 2
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

@pytest.fixture(autouse=True)
async def wrap_registry(monkeypatch):
    mock_class = Mock(side_effect=lambda : Mock(wraps=Registry()))
    monkeypatch.setattr('nextline.state.Registry', mock_class)
    yield

##__________________________________________________________________||
@pytest.fixture(params=[True, False])
def callback(request):
    if request.param:
        y = Mock()
    else:
        y = None
    yield y

@pytest.fixture()
async def initialized(callback):
    y = Initialized(SOURCE_ONE, callback)
    yield y

@pytest.fixture()
async def running(initialized):
    y = initialized.run()
    yield y

@pytest.fixture()
async def exited(running):
    await running._event_exited.wait()
    y = running._state_exited
    yield y

@pytest.fixture()
async def finished(exited):
    y = await exited.finish()
    yield y

@pytest.fixture()
async def closed(finished):
    y = await finished.close()
    yield y

params_statement = (pytest.param(SOURCE_TWO, id="SOURCE_TWO"), None)

##__________________________________________________________________||
class BaseTestState(ABC):

    @abstractmethod
    def state(self, *_, **__):
        pass

    @pytest.mark.asyncio
    async def test_state(self, state):
        assert isinstance(state, self.state_class)
        assert 'obsolete' not in repr(state)

    async def assert_obsolete(self, state):
        assert 'obsolete' in repr(state)

        with pytest.raises(StateObsoleteError):
            state.run()

        with pytest.raises(StateObsoleteError):
            state.reset()

        with pytest.raises(StateObsoleteError):
            await state.close()

    @pytest.mark.asyncio
    async def test_run(self, state):
        with pytest.raises(StateMethodError):
            state.run()

    @pytest.mark.parametrize('statement', params_statement)
    @pytest.mark.asyncio
    async def test_reset(self, state, statement):
        if statement:
            kwargs = dict(statement=statement)
        else:
            kwargs = dict()
        with pytest.raises(StateMethodError):
            reset = state.reset(**kwargs)

class TestInitialized(BaseTestState):

    state_class = Initialized

    @pytest.fixture()
    def state(self, initialized):
        yield initialized

    @pytest.mark.asyncio
    async def test_run(self, state):
        running = state.run()
        assert isinstance(running, Running)
        await self.assert_obsolete(state)

    @pytest.mark.parametrize('statement', params_statement)
    @pytest.mark.asyncio
    async def test_reset(self, state, statement):

        initial_statement = state.registry.get_statement()

        if statement:
            expected_statement = statement
            kwargs = dict(statement=statement)
        else:
            expected_statement = initial_statement
            kwargs = dict()

        reset = state.reset(**kwargs)

        assert isinstance(reset, Initialized)
        assert reset is not state

        assert expected_statement == reset.registry.get_statement()

        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_send_pdb_command(self, state):
        with pytest.raises(StateMethodError):
            state.send_pdb_command()

    @pytest.mark.asyncio
    async def test_exception(self, state):
        with pytest.raises(StateMethodError):
            state.exception()

    @pytest.mark.asyncio
    async def test_result(self, state):
        with pytest.raises(StateMethodError):
            state.result()

class TestRunning(BaseTestState):

    state_class = Running

    @pytest.fixture()
    def state(self, running):
        yield running

class TestExited(BaseTestState):

    state_class = Exited

    @pytest.fixture()
    def state(self, exited):
        yield exited

class TestFinished(BaseTestState):

    state_class = Finished

    @pytest.fixture()
    def state(self, finished):
        yield finished

    @pytest.mark.parametrize('statement', params_statement)
    @pytest.mark.asyncio
    async def test_reset(self, state, statement):

        initial_statement = state.registry.get_statement()

        if statement:
            expected_statement = statement
            kwargs = dict(statement=statement)
        else:
            expected_statement = initial_statement
            kwargs = dict()

        reset = state.reset(**kwargs)

        assert isinstance(reset, Initialized)

        assert expected_statement == reset.registry.get_statement()

        await self.assert_obsolete(state)

class TestClosed(BaseTestState):

    state_class = Closed

    @pytest.fixture()
    def state(self, closed):
        yield closed

@pytest.mark.asyncio
async def test_running(running):
    assert isinstance(running, Running)

@pytest.mark.asyncio
async def test_exited(exited, callback):
    assert isinstance(exited, Exited)

@pytest.mark.asyncio
async def test_finished(finished):
    assert isinstance(finished, Finished)
    assert 'obsolete' not in repr(finished)

@pytest.mark.asyncio
async def test_finished_finish(finished):
    # The same object should be returned no matter
    # how many times called.
    assert finished is await finished.finish()
    assert finished is await finished.finish()

    assert 'obsolete' not in repr(finished)

@pytest.mark.asyncio
async def test_finished_reset(finished):

    initialized = finished.reset()
    assert isinstance(initialized, Initialized)
    assert 'obsolete' in repr(finished)

    with pytest.raises(StateObsoleteError):
        await finished.finish()

    with pytest.raises(StateObsoleteError):
        finished.reset()

    with pytest.raises(StateObsoleteError):
        await finished.close()

@pytest.mark.asyncio
async def test_finished_close(finished):

    closed = await finished.close()
    assert isinstance(closed, Closed)
    assert 'obsolete' in repr(finished)

    with pytest.raises(StateObsoleteError):
        await finished.finish()

    with pytest.raises(StateObsoleteError):
        finished.reset()

    with pytest.raises(StateObsoleteError):
        await finished.close()

@pytest.mark.asyncio
async def test_closed(closed):
    assert isinstance(closed, Closed)
    assert 'obsolete' not in repr(finished)

@pytest.mark.asyncio
async def test_closed_close(closed):
    # The same object should be returned no matter
    # how many times called.
    assert closed is await closed.close()

    assert 'obsolete' not in repr(closed)

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_transition():

    state = Initialized(SOURCE_ONE)
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

    state = Initialized(SOURCE_ONE, exited=callback)
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
async def test_transition_once():

    callback = Mock()

    initialized = Initialized(SOURCE_ONE, exited=callback)
    assert isinstance(initialized, Initialized)

    running = initialized.run()
    assert isinstance(running, Running)

    finished = await running.finish()
    assert isinstance(finished, Finished)

    assert finished is await running.finish() # the same object

    closed = await finished.close()
    assert isinstance(closed, Closed)

    # The existed state is received by the callback
    assert 1 == callback.call_count
    exited, *_ = callback.call_args.args
    assert isinstance(exited, Exited)

    assert finished is await exited.finish() # the same object

@pytest.mark.asyncio
async def test_exited_callback_raise():

    callback = Mock(side_effect=Exception('ntYpOsermaRb'))

    state = Initialized(SOURCE_ONE, exited=callback)
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
async def test_register_state_name():
    state = Initialized(SOURCE_ONE)
    state = state.run()
    state = await state.finish()
    state = await state.close()

    expected = ['initialized', 'running', 'exited', 'finished', 'closed']
    actual = [a.args[0] for a in state.registry.register_state_name.call_args_list]
    assert expected == actual

@pytest.mark.asyncio
async def test_register_state_name():
    state = Initialized(SOURCE_ONE)
    state = state.run()
    state = await state.finish()
    state = state.reset()
    state = state.run()
    state = await state.finish()
    state = await state.close()

    expected = [
        'initialized', 'running', 'exited', 'finished',
        'initialized', 'running', 'exited', 'finished', 'closed'
    ]
    actual = [a.args[0] for a in state.registry.register_state_name.call_args_list]
    assert expected == actual

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_finished_exception():
    state = Initialized(SOURCE_RAISE)
    state = state.run()

    state = await state.finish()
    assert isinstance(state, Finished)

    assert isinstance(state.exception(), Exception)
    assert ('foo', 'bar') == state.exception().args
    with pytest.raises(Exception):
        raise state.exception()

@pytest.mark.asyncio
async def test_finished_exception_none():
    state = Initialized(SOURCE_ONE)
    state = state.run()
    state = await state.finish()
    assert isinstance(state, Finished)

    assert state.exception() is None

@pytest.mark.asyncio
async def test_finished_result():
    state = Initialized(SOURCE_ONE)
    state = state.run()

    state = await state.finish()
    assert isinstance(state, Finished)

    assert state.result() is None

@pytest.mark.asyncio
async def test_finished_result_raise():
    state = Initialized(SOURCE_RAISE)
    state = state.run()

    state = await state.finish()
    assert isinstance(state, Finished)

    with pytest.raises(Exception):
        state.result()

##__________________________________________________________________||
