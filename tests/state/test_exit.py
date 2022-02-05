import pytest

from nextline.state import Exited, Finished

from .base import BaseTestState


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
