import pytest

from nextline.state import Running, Exited, StateObsoleteError

from .base import BaseTestState


class TestRunning(BaseTestState):

    state_class = Running

    @pytest.fixture()
    def state(self, running):
        yield running

    async def assert_obsolete(self, state):
        assert "obsolete" in repr(state)

        with pytest.raises(StateObsoleteError):
            state.run()

        with pytest.raises(StateObsoleteError):
            await state.finish()

        with pytest.raises(StateObsoleteError):
            state.reset()

        with pytest.raises(StateObsoleteError):
            await state.close()

    def test_registry_state_name(self, state):
        assert state.registry.get("state_name") in (Running.name, Exited.name)

    @pytest.mark.asyncio
    async def test_exited(self, state):
        # exited() can be called multiple times
        exited = await state.exited()
        assert isinstance(exited, Exited)
        assert exited is await state.exited()
        assert exited is await state.exited()

        await self.assert_obsolete(state)

    def test_send_pdb_command(self, state):
        pass
