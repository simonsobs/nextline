import pytest

from unittest.mock import Mock

from nextline.registry import PdbCIRegistry


@pytest.fixture(autouse=True)
def monkey_patch_trace(monkeypatch):
    """Mock the class Trace in the module nextline.state"""
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_instance.pdb_ci_registry = Mock(spec=PdbCIRegistry)
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr("nextline.state.Trace", mock_class)
    yield mock_class
