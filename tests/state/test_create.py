from __future__ import annotations

import pytest

from nextline.state import State, Created, Initialized, Closed

from .base import BaseTestState


class TestCreated(BaseTestState):

    state_class = Created

    @pytest.fixture()
    def state(self, created: State) -> State:
        return created

    async def test_initialize(self, state: State):
        initialized = await state.initialize()
        assert isinstance(initialized, Initialized)
        await self.assert_obsolete(state)

    async def test_close(self, state: State):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)
