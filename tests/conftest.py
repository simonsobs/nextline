import sys
import threading
import pytest
from unittest.mock import Mock


@pytest.fixture(autouse=True)
def recover_trace():
    """Set the original trace function back after each test"""
    trace_org = sys.gettrace()
    yield
    sys.settrace(trace_org)
    threading.settrace(trace_org)


@pytest.fixture
def monkey_patch_trace(monkeypatch):
    """Mock the class Trace in the module nextline.run"""
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr("nextline.process.run.Trace", mock_class)
    yield mock_class
