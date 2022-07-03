from __future__ import annotations

import pytest
from unittest.mock import Mock, call

from nextline.state import State, Running, Finished

from .base import BaseTestState


class TestRunning(BaseTestState):

    state_class = Running

    @pytest.fixture()
    def state(self, running: State) -> State:
        return running

    def test_state(self, state: State, context: Mock):
        super().test_state(state, context)
        assert [call(state)] == context.run.call_args_list

    async def test_finish(self, state):
        finished = await state.finish()
        assert isinstance(finished, Finished)
        await self.assert_obsolete(state)
