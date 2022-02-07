import pytest

from nextline.state import Initialized, Running, Closed

from .base import BaseTestState


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
        exited = await running.exited()
        finished = await exited.finish()
        finished.close()

    @pytest.mark.asyncio
    async def test_reset(self, state):
        reset = state.reset()
        assert isinstance(reset, Initialized)
        assert reset is not state
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        closed = state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)
