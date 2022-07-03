from __future__ import annotations

import pytest
from unittest.mock import Mock, call

from nextline.state import State, Closed

from .base import BaseTestState


class TestClosed(BaseTestState):

    state_class = Closed

    @pytest.fixture()
    def state(self, closed: State) -> State:
        return closed

    def test_state(self, state: State, context: Mock):
        super().test_state(state, context)
        assert [call(state)] == context.close.call_args_list

    async def test_close(self, state: State):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.close()
        assert state is await state.close()
        assert state is await state.close()
        assert "obsolete" not in repr(state)
