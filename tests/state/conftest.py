import pytest
from unittest.mock import Mock

from nextline.utils import ExcThread
from queue import Queue


@pytest.fixture(autouse=True)
def monkey_patch_mp(monkeypatch):
    class mock_context:
        Queue = Queue
        Process = ExcThread

    monkeypatch.setattr("nextline.state._mp", mock_context)
    return


@pytest.fixture
def monkey_patch_run(monkeypatch):
    def mock_run(registry, q_commands, q_done) -> None:
        del registry, q_commands
        q_done.put((None, None))

    wrap = Mock(wraps=mock_run)
    monkeypatch.setattr("nextline.state.run", wrap)
    yield wrap
