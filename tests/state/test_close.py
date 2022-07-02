import pytest

from nextline.state import State, Closed

from .base import BaseTestState


class TestClosed(BaseTestState):

    state_class = Closed

    @pytest.fixture()
    def state(self, closed: State) -> State:
        return closed

    async def test_close(self, state: State):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.close()
        assert state is await state.close()
        assert state is await state.close()
        assert "obsolete" not in repr(state)
