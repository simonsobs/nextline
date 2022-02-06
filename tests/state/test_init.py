import pytest

from nextline.state import Initialized, Running, Closed

from .base import BaseTestState


class TestInitialized(BaseTestState):

    state_class = Initialized

    @pytest.fixture()
    def state(self, initialized):
        yield initialized

    def test_sync(self, statement):
        # requires a running asyncio event loop
        with pytest.raises(RuntimeError):
            _ = Initialized(statement)

    @pytest.mark.asyncio
    async def test_run(self, state):
        running = state.run()
        assert isinstance(running, Running)
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_reset(self, state, statements_for_test_reset):
        expected_statement, statement = statements_for_test_reset

        reset = state.reset(statement=statement)
        assert isinstance(reset, Initialized)

        assert expected_statement == reset.registry.get("statement")

        assert reset is not state
        assert reset.registry is state.registry

        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)
