import pytest

from nextline.state import Running, Finished, StateObsoleteError

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

    @pytest.mark.asyncio
    async def test_finish(self, state):
        finished = await state.finish()
        assert isinstance(finished, Finished)
        await self.assert_obsolete(state)

    def test_send_pdb_command(self, state):
        pass
