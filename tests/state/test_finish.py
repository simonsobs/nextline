import pytest

from nextline.state import Initialized, Finished, Closed

from .base import BaseTestState

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()


class TestFinished(BaseTestState):

    state_class = Finished

    @pytest.fixture()
    def state(self, finished):
        yield finished

    @pytest.mark.asyncio
    async def test_finish(self, state):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.finish()
        assert state is await state.finish()
        assert state is await state.finish()
        assert "obsolete" not in repr(state)

    @pytest.mark.asyncio
    async def test_reset(self, state, statements_for_test_reset):
        expected_statement, statement = statements_for_test_reset

        reset = state.reset(statement=statement)
        assert isinstance(reset, Initialized)

        assert expected_statement == reset.registry.get("statement")

        assert reset.registry is state.registry

        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_exception(self, state):
        assert state.exception() is None

    @pytest.mark.asyncio
    async def test_result(self, state):
        assert state.result() is None

    @pytest.mark.asyncio
    async def test_exception_raise(self):
        state = Initialized(SOURCE_RAISE)
        state = state.run()

        state = await state.exited()
        state = await state.finish()
        assert isinstance(state, Finished)

        assert isinstance(state.exception(), Exception)
        assert ("foo", "bar") == state.exception().args
        with pytest.raises(Exception):
            raise state.exception()

    @pytest.mark.asyncio
    async def test_result_raise(self):
        state = Initialized(SOURCE_RAISE)
        state = state.run()

        state = await state.exited()
        state = await state.finish()
        assert isinstance(state, Finished)

        with pytest.raises(Exception):
            state.result()
