from __future__ import annotations

import pytest

from nextline.state import State, Initialized, Running, Closed

from .base import BaseTestState


class TestInitialized(BaseTestState):

    state_class = Initialized

    @pytest.fixture()
    def state(self, initialized: State) -> State:
        return initialized

    @pytest.mark.asyncio
    async def test_run(self, state: State):
        running = state.run()
        assert isinstance(running, Running)
        await self.assert_obsolete(state)
        finished = await running.finish()
        finished.close()

    @pytest.mark.asyncio
    async def test_reset(self, state: State):
        reset = state.reset()
        assert isinstance(reset, Initialized)
        assert reset is not state
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state: State):
        closed = state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)
