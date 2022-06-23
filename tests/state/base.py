from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Generator, Tuple

import pytest
from unittest.mock import Mock

from nextline.state import (
    State,
    Initialized,
    Running,
    Finished,
    Closed,
    StateObsoleteError,
    StateMethodError,
)
from nextline.process.run import QueueCommands, QueueDone, QueueLogging, RunArg
from nextline.types import PromptNo, TraceNo


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

    @pytest.fixture(autouse=True)
    def mock_run(
        self,
        monkeypatch,
        mock_run_result_exception: Tuple[Any, Any],
    ):
        def run(
            run_arg: RunArg,
            q_commands: QueueCommands,
            q_done: QueueDone,
            q_logging: QueueLogging,
        ) -> None:
            del run_arg, q_commands, q_logging
            q_done.put(mock_run_result_exception)

        wrap = Mock(wraps=run)
        monkeypatch.setattr("nextline.state.run", wrap)
        return wrap

    @pytest.fixture
    def context(self) -> RunArg:
        y = RunArg()
        return y

    @pytest.fixture()
    def initialized(
        self, context: RunArg
    ) -> Generator[Initialized, None, None]:
        y = Initialized(context=context)
        yield y
        if y.is_obsolete():
            return
        y.close()

    @pytest.fixture()
    async def running(
        self, initialized: Initialized
    ) -> AsyncGenerator[Running, None]:
        y = initialized.run()
        yield y
        if y.is_obsolete():
            return
        finished = await y.finish()
        finished.close()

    @pytest.fixture()
    async def finished(
        self, running: Running
    ) -> AsyncGenerator[Finished, None]:
        y = await running.finish()
        yield y
        if y.is_obsolete():
            return
        y.close()

    @pytest.fixture()
    def closed(self, finished: Finished) -> Closed:
        y = finished.close()
        return y

    @abstractmethod
    def state(self, _):
        """Yield an instance of the class being tested

        To be overridden as a pytest fixture.
        """
        pass

    def test_state(self, state: State):
        assert self.state_class is not None
        assert isinstance(state, self.state_class)
        assert "obsolete" not in repr(state)

    async def assert_obsolete(self, state: State):
        assert "obsolete" in repr(state)

        with pytest.raises(StateObsoleteError):
            state.run()

        with pytest.raises(StateObsoleteError):
            await state.finish()

        with pytest.raises(StateObsoleteError):
            state.reset()

        with pytest.raises(StateObsoleteError):
            state.close()

    def test_run(self, state: State):
        with pytest.raises(StateMethodError):
            state.run()

    @pytest.mark.asyncio
    async def test_finish(self, state: State):
        with pytest.raises(StateMethodError):
            await state.finish()

    def test_reset(self, state: State):
        with pytest.raises(StateMethodError):
            state.reset()

    def test_send_pdb_command(self, state: State):
        trace_no = TraceNo(1)
        prompt_no = PromptNo(1)
        command = "next"
        with pytest.raises(StateMethodError):
            state.send_pdb_command(command, prompt_no, trace_no)

    def test_exception(self, state: State):
        with pytest.raises(StateMethodError):
            state.exception()

    def test_result(self, state: State):
        with pytest.raises(StateMethodError):
            state.result()
