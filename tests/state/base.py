from abc import ABC, abstractmethod
import itertools

import pytest

from nextline.state import Initialized, StateObsoleteError, StateMethodError
from nextline.utils import Registry

SOURCE_ONE = """
import time
time.sleep(0.001)
""".strip()


class BaseTestState(ABC):
    """Test state classes of the state machine

    To be inherited by the test class for each state class.
    """

    @pytest.fixture()
    def statement(self):
        yield SOURCE_ONE

    @pytest.fixture()
    async def registry(self, statement):
        y = Registry()
        y.open_register("statement")
        y.open_register("state_name")
        y.open_register("run_no")
        y.open_register("run_no_count")
        y.register("statement", statement)
        y.register("run_no_count", itertools.count().__next__)
        yield y
        await y.close()

    @pytest.fixture()
    async def initialized(self, registry):
        y = Initialized(registry=registry)
        yield y
        if y.is_obsolete():
            return
        y.close()

    @pytest.fixture()
    async def running(self, initialized):
        y = initialized.run()
        yield y
        if y.is_obsolete():
            return
        exited = await y.exited()
        if exited.is_obsolete():
            return
        finished = await exited.finish()
        finished.close()

    @pytest.fixture()
    async def exited(self, running):
        y = await running.exited()
        yield y
        if y.is_obsolete():
            return
        finished = await y.finish()
        finished.close()

    @pytest.fixture()
    async def finished(self, exited):
        y = await exited.finish()
        yield y
        if y.is_obsolete():
            return
        y.close()

    @pytest.fixture()
    async def closed(self, finished):
        y = finished.close()
        yield y

    @abstractmethod
    def state(self, *_, **__):
        """Yield an instance of the class being tested

        To be overridden as a pytest fixture.
        """
        pass

    def test_state(self, state):
        assert isinstance(state, self.state_class)
        assert "obsolete" not in repr(state)

    def test_registry_state_name(self, state):
        assert self.state_class.name == state.registry.get("state_name")

    async def assert_obsolete(self, state):
        assert "obsolete" in repr(state)

        with pytest.raises(StateObsoleteError):
            state.run()

        with pytest.raises(StateObsoleteError):
            await state.exited()

        with pytest.raises(StateObsoleteError):
            await state.finish()

        with pytest.raises(StateObsoleteError):
            state.reset()

        with pytest.raises(StateObsoleteError):
            state.close()

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

    @pytest.mark.asyncio
    async def test_reset(self, state):
        with pytest.raises(StateMethodError):
            state.reset()

    def test_send_pdb_command(self, state):
        thread_asynctask_id = (1, None)
        command = "next"
        with pytest.raises(StateMethodError):
            state.send_pdb_command(thread_asynctask_id, command)

    def test_exception(self, state):
        with pytest.raises(StateMethodError):
            state.exception()

    def test_result(self, state):
        with pytest.raises(StateMethodError):
            state.result()
