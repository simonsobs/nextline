from __future__ import annotations

import sys
from abc import ABC, abstractmethod
import itertools
from typing import Any, AsyncGenerator

import pytest

from nextline.state import (
    State,
    Initialized,
    Running,
    Finished,
    Closed,
    StateObsoleteError,
    StateMethodError,
)
from nextline.utils import SubscribableDict, ThreadTaskIdComposer

SOURCE_ONE = """
import time
time.sleep(0.001)
""".strip()


class BaseTestState(ABC):
    """Test state classes of the state machine

    To be inherited by the test class for each state class.
    """

    state_class: Any = None

    @pytest.fixture()
    def statement(self):
        yield SOURCE_ONE

    @pytest.fixture()
    def registry(self, statement):
        y = SubscribableDict()
        y["statement"] = statement
        y["run_no_count"] = itertools.count().__next__
        y["trace_id_factory"] = ThreadTaskIdComposer()
        y["create_capture_stdout"] = lambda _: sys.stdout
        yield y
        y.close()

    @pytest.fixture()
    async def initialized(
        self, registry: SubscribableDict
    ) -> AsyncGenerator[Initialized, None]:
        y = Initialized(registry=registry)
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
    async def closed(self, finished: Finished) -> AsyncGenerator[Closed, None]:
        y = finished.close()
        yield y

    @abstractmethod
    def state(self, *_, **__):
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

    @pytest.mark.asyncio
    async def test_reset(self, state: State):
        with pytest.raises(StateMethodError):
            state.reset()

    def test_send_pdb_command(self, state: State):
        trace_id = 1
        command = "next"
        with pytest.raises(StateMethodError):
            state.send_pdb_command(trace_id, command)

    def test_exception(self, state: State):
        with pytest.raises(StateMethodError):
            state.exception()

    def test_result(self, state: State):
        with pytest.raises(StateMethodError):
            state.result()
