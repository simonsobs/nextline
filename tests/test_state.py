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
class BaseTestState(ABC):

    @pytest.fixture()
    def statement(self):
        yield SOURCE_ONE

    @pytest.fixture()
    async def initialized(self, statement):
        y = Initialized(statement)
        yield y

    @pytest.fixture()
    async def running(self, initialized):
        y = initialized.run()
        yield y

    @pytest.fixture()
    async def exited(self, running):
        y = await running.exited()
        yield y

    @pytest.fixture()
    async def finished(self, exited):
        y = await exited.finish()
        yield y

    @pytest.fixture()
    async def closed(self, finished):
        y = await finished.close()
        yield y

    @abstractmethod
    def state(self, *_, **__):
        pass

    params = (pytest.param(SOURCE_TWO, id="SOURCE_TWO"), None)
    @pytest.fixture(params=params)
    def statement_for_test_reset(self, request):
        yield request.param

    def test_state(self, state):
        assert isinstance(state, self.state_class)
        assert 'obsolete' not in repr(state)

    async def assert_obsolete(self, state):
        assert 'obsolete' in repr(state)

        with pytest.raises(StateObsoleteError):
            state.run()

        with pytest.raises(StateObsoleteError):
            await state.exited()

        with pytest.raises(StateObsoleteError):
            await state.finish()

        with pytest.raises(StateObsoleteError):
            state.reset()

        with pytest.raises(StateObsoleteError):
            await state.close()

    def test_run(self, state):
        with pytest.raises(StateMethodError):
            state.run()

    @pytest.mark.asyncio
    async def test_exited(self, state):
        with pytest.raises(StateMethodError):
            await state.exited()

    @pytest.mark.asyncio
    async def test_finish(self, state):
        with pytest.raises(StateMethodError):
            await state.finish()

    def test_reset(self, state, statement_for_test_reset):
        statement = statement_for_test_reset
        if statement:
            kwargs = dict(statement=statement)
        else:
            kwargs = dict()
        with pytest.raises(StateMethodError):
            reset = state.reset(**kwargs)

    def test_send_pdb_command(self, state):
        thread_asynctask_id = (1, None)
        command = 'next'
        with pytest.raises(StateMethodError):
            state.send_pdb_command(thread_asynctask_id, command)

    def test_exception(self, state):
        with pytest.raises(StateMethodError):
            state.exception()

    def test_result(self, state):
        with pytest.raises(StateMethodError):
            state.result()

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

    @pytest.mark.asyncio
    async def test_reset(self, state, statement_for_test_reset):

        statement = statement_for_test_reset
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
        assert reset.registry is state.registry

        assert expected_statement == reset.registry.get_statement()

        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)

class TestRunning(BaseTestState):

    state_class = Running

    @pytest.fixture()
    def state(self, running):
        yield running

    @pytest.mark.asyncio
    async def test_exited(self, state):
        exited = await state.exited()
        assert isinstance(exited, Exited)

    @pytest.mark.asyncio
    async def test_finish(self, state):
        finished = await state.finish()
        assert isinstance(finished, Finished)
        await self.assert_obsolete(state)

    def test_send_pdb_command(self, state):
        pass

class TestExited(BaseTestState):

    state_class = Exited

    @pytest.fixture()
    def state(self, exited):
        yield exited

    @pytest.mark.asyncio
    async def test_finish(self, state):
        finished = await state.finish()
        assert isinstance(finished, Finished)
        await self.assert_obsolete(state)

class TestFinished(BaseTestState):

    state_class = Finished

    @pytest.fixture()
    def state(self, finished):
        yield finished

    @pytest.mark.asyncio
    async def test_finish(self, state):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.finish()
        assert state is await state.finish()
        assert state is await state.finish()
        assert 'obsolete' not in repr(state)

    @pytest.mark.asyncio
    async def test_reset(self, state, statement_for_test_reset):

        statement = statement_for_test_reset
        initial_statement = state.registry.get_statement()

        if statement:
            expected_statement = statement
            kwargs = dict(statement=statement)
        else:
            expected_statement = initial_statement
            kwargs = dict()

        reset = state.reset(**kwargs)

        assert isinstance(reset, Initialized)
        assert reset.registry is state.registry

        assert expected_statement == reset.registry.get_statement()

        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_exception(self, state):
        assert state.exception() is None

    @pytest.mark.asyncio
    async def test_result(self, state):
        assert state.result() is None

    @pytest.mark.asyncio
    async def test_exception_raise(self):
        state = Initialized(SOURCE_RAISE)
        state = state.run()

        state = await state.finish()
        assert isinstance(state, Finished)

        assert isinstance(state.exception(), Exception)
        assert ('foo', 'bar') == state.exception().args
        with pytest.raises(Exception):
            raise state.exception()

    @pytest.mark.asyncio
    async def test_result_raise(self):
        state = Initialized(SOURCE_RAISE)
        state = state.run()

        state = await state.finish()
        assert isinstance(state, Finished)

        with pytest.raises(Exception):
            state.result()

class TestClosed(BaseTestState):

    state_class = Closed

    @pytest.fixture()
    def state(self, closed):
        yield closed

    @pytest.mark.asyncio
    async def test_reset(self, state, statement_for_test_reset):

        statement = statement_for_test_reset
        initial_statement = state.registry.get_statement()

        if statement:
            expected_statement = statement
            kwargs = dict(statement=statement)
        else:
            expected_statement = initial_statement
            kwargs = dict()

        reset = state.reset(**kwargs)

        assert isinstance(reset, Initialized)
        assert reset.registry is not state.registry

        assert expected_statement == reset.registry.get_statement()

        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.close()
        assert state is await state.close()
        assert state is await state.close()
        assert 'obsolete' not in repr(state)

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
