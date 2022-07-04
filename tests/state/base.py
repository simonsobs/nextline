from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Tuple

import pytest
from unittest.mock import Mock

from nextline.context import Context
from nextline.state import (
    State,
    Created,
    Initialized,
    Running,
    Finished,
    Closed,
    StateObsoleteError,
    StateMethodError,
)


class BaseTestState(ABC):
    """Test state classes of the state machine

    To be inherited by the test class for each state class.
    """

    state_class: Any = None

    @pytest.fixture
    def mock_run_exception(self) -> Any:
        return None

    @pytest.fixture
    def mock_run_result_exception(self, mock_run_exception) -> Tuple[Any, Any]:
        result = None
        return result, mock_run_exception

    @pytest.fixture
    def context(
        self,
        mock_run_result_exception: Tuple[Any, Any],
    ) -> Context:
        y = Mock(spec=Context)
        y.result, y.exception = mock_run_result_exception
        return y

    @pytest.fixture
    def created(self, context: Context) -> Created:
        return Created(context)

    @pytest.fixture
    async def initialized(self, created: Created) -> Initialized:
        return await created.initialize()

    @pytest.fixture
    async def running(self, initialized: Initialized) -> Running:
        return await initialized.run()

    @pytest.fixture()
    async def finished(self, running: Running) -> Finished:
        return await running.finish()

    @pytest.fixture()
    async def closed(self, finished: Finished) -> Closed:
        return await finished.close()

    @abstractmethod
    def state(self, _):
        """Yield an instance of the class being tested

        To be overridden as a pytest fixture.
        """
        pass

    def test_state(self, state: State, context: Mock):
        del context
        assert self.state_class is not None
        assert isinstance(state, self.state_class)
        assert "obsolete" not in repr(state)

    async def assert_obsolete(self, state: State):
        assert "obsolete" in repr(state)

        with pytest.raises(StateObsoleteError):
            await state.run()

        with pytest.raises(StateObsoleteError):
            await state.finish()

        with pytest.raises(StateObsoleteError):
            await state.reset()

        with pytest.raises(StateObsoleteError):
            await state.close()

    async def test_initialize(self, state: State):
        with pytest.raises(StateMethodError):
            await state.initialize()

    async def test_run(self, state: State):
        with pytest.raises(StateMethodError):
            await state.run()

    async def test_finish(self, state: State):
        with pytest.raises(StateMethodError):
            await state.finish()

    async def test_reset(self, state: State):
        with pytest.raises(StateMethodError):
            await state.reset()

    def test_exception(self, state: State):
        with pytest.raises(StateMethodError):
            state.exception()

    def test_result(self, state: State):
        with pytest.raises(StateMethodError):
            state.result()
