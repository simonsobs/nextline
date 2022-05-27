from __future__ import annotations

import pytest

from typing import Any

from nextline.state import State, Initialized, Finished, Closed

from .base import BaseTestState


class MockError(Exception):
    pass


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
    async def test_exception(self, state: State, mock_run_exception):
        assert state.exception() is mock_run_exception

    @pytest.mark.asyncio
    async def test_result(self, state: State, mock_run_exception):
        if mock_run_exception is None:
            assert state.result() is None
        else:
            with pytest.raises(mock_run_exception):
                state.result()

    @pytest.fixture(params=[None, MockError])
    def mock_run_exception(self, request) -> Any:  # type: ignore
        return request.param
