from __future__ import annotations

import pytest
from unittest.mock import Mock, call, sentinel

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

    def test_state(self, state: State, context: Mock):
        super().test_state(state, context)
        assert [call(state)] == context.finish.call_args_list

    async def test_finish(self, state: State):
        # The same object should be returned no matter
        # how many times called.
        assert state is await state.finish()
        assert state is await state.finish()
        assert state is await state.finish()
        assert "obsolete" not in repr(state)

    async def test_reset(self, state: State, context: Mock):  # type: ignore
        reset = await state.reset(sentinel.args)
        assert isinstance(reset, Initialized)
        await self.assert_obsolete(state)
        assert [call(sentinel.args)] == context.reset.call_args_list

    async def test_close(self, state: State):
        closed = await state.close()
        assert isinstance(closed, Closed)
        await self.assert_obsolete(state)

    async def test_exception(self, state: State, mock_run_exception):  # type: ignore
        assert state.exception() is mock_run_exception

    async def test_result(self, state: State, mock_run_exception):  # type: ignore
        if mock_run_exception is None:
            assert state.result() is None
        else:
            with pytest.raises(mock_run_exception):
                state.result()

    @pytest.fixture(params=[None, MockError])
    def mock_run_exception(self, request) -> Any:  # type: ignore
        return request.param
