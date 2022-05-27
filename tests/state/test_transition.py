import itertools

import pytest
from unittest.mock import Mock

from nextline.state import Initialized, Running, Finished, Closed
from nextline.utils import SubscribableDict, ThreadTaskIdComposer
from nextline.run import QCommands, QDone


@pytest.fixture()
def registry():
    y = SubscribableDict()
    y["run_no_count"] = itertools.count().__next__
    y["trace_id_factory"] = ThreadTaskIdComposer()
    yield y
    y.close()


@pytest.mark.asyncio
async def test_transition(registry):

    state = Initialized(registry=registry)
    assert isinstance(state, Initialized)

    state = state.run()
    assert isinstance(state, Running)

    state = await state.finish()
    assert isinstance(state, Finished)

    state = state.close()
    assert isinstance(state, Closed)


@pytest.fixture(autouse=True)
def monkey_patch_run(monkeypatch):
    def mock_run(
        registry: SubscribableDict,
        q_commands: QCommands,
        q_done: QDone,
    ) -> None:
        del registry, q_commands
        q_done.put((None, None))

    wrap = Mock(wraps=mock_run)
    monkeypatch.setattr("nextline.state.run", wrap)
    yield wrap
