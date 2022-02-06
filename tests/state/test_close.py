import pytest

from nextline.state import Closed

from .base import BaseTestState


class TestClosed(BaseTestState):

    state_class = Closed

    @pytest.fixture()
    def state(self, closed):
        yield closed

    def test_registry_state_name(self, state):
        # assert self.state_class.name == state.registry.get("state_name")

        # As the registry is already closed, test with the call to the
        # wrapping mock object.
        registered_state_name = [
            c.args[1]
            for c in state.registry.register.call_args_list
            if c.args[0] == "state_name"
        ][-1]
        assert self.state_class.name == registered_state_name

    @pytest.mark.asyncio
    async def test_close(self, state):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.close()
        assert state is await state.close()
        assert state is await state.close()
        assert "obsolete" not in repr(state)
