from __future__ import annotations

import pytest

from nextline.state import State, Running, Finished, StateObsoleteError
from nextline.types import TraceNo

from .base import BaseTestState


class TestRunning(BaseTestState):

    state_class = Running

    @pytest.fixture()
    def state(self, running: State) -> State:
        return running

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

    @pytest.mark.asyncio
    async def test_finish(self, state):
        finished = await state.finish()
        assert isinstance(finished, Finished)
        await self.assert_obsolete(state)

    def test_run_called(self, state: State, mock_run):
        del state
        assert mock_run.call_count == 1
        registry, q_commands, q_done = mock_run.call_args.args
        del registry, q_commands, q_done

    def test_send_pdb_command(self, state: State, mock_run):  # type: ignore
        trace_id = TraceNo(1)
        command = "next"
        state.send_pdb_command(trace_id, command)
        _, q_commands, _ = mock_run.call_args.args
        assert (trace_id, command) == q_commands.get()
