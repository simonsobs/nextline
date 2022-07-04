from __future__ import annotations

import pytest
from unittest.mock import Mock, call, sentinel

from nextline.state import State, Initialized, Running, Closed

from .base import BaseTestState


class TestInitialized(BaseTestState):

    state_class = Initialized

    @pytest.fixture()
    def state(self, initialized: State) -> State:
        return initialized

    def test_state(self, state: State, context: Mock):
        super().test_state(state, context)
        assert [call.initialize(state)] == context.mock_calls

    async def test_run(self, state: State):
        running = await state.run()
        assert isinstance(running, Running)
        await self.assert_obsolete(state)

    async def test_reset(self, state: State, context: Mock):  # type: ignore
        reset = await state.reset(sentinel.args)
        assert isinstance(reset, Initialized)
        assert reset is not state
        await self.assert_obsolete(state)
        assert [call(sentinel.args)] == context.reset.call_args_list

    async def test_close(self, state: State):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)
