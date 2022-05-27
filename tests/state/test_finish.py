from __future__ import annotations

import pytest

from nextline.state import State, Initialized, Finished, Closed
from nextline.utils import SubscribableDict

from .base import BaseTestState

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()

SOURCE_INVALID_SYNTAX = """
def
""".strip()


class TestFinished(BaseTestState):

    state_class = Finished

    @pytest.fixture()
    def state(self, finished: State) -> State:
        return finished

    @pytest.mark.asyncio
    async def test_finish(self, state: State):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.finish()
        assert state is await state.finish()
        assert state is await state.finish()
        assert "obsolete" not in repr(state)

    @pytest.mark.asyncio
    async def test_reset(self, state: State):
        reset = state.reset()
        assert isinstance(reset, Initialized)
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_close(self, state: State):
        closed = state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)

    @pytest.mark.asyncio
    async def test_exception(self, state: State):
        assert state.exception() is None

    @pytest.mark.asyncio
    async def test_result(self, state: State):
        assert state.result() is None

    params = [
        pytest.param(SOURCE_RAISE, Exception, id="raise"),
        pytest.param(SOURCE_INVALID_SYNTAX, SyntaxError, id="invalid-syntax"),
    ]

    @pytest.mark.parametrize("source, exc", params)
    @pytest.mark.asyncio
    async def test_exception_raise(
        self, registry: SubscribableDict, source, exc
    ):
        registry["statement"] = source

        state: State = Initialized(registry=registry)
        state = state.run()

        state = await state.finish()
        assert isinstance(state, Finished)

        assert isinstance(state.exception(), exc)
        # assert ("foo", "bar") == state.exception().args
        with pytest.raises(exc):
            raise state.exception()

    @pytest.mark.parametrize("source, exc", params)
    @pytest.mark.asyncio
    async def test_result_raise(self, registry: SubscribableDict, source, exc):
        registry["statement"] = source

        state: State = Initialized(registry=registry)
        state = state.run()

        state = await state.finish()
        assert isinstance(state, Finished)

        with pytest.raises(exc):
            state.result()
