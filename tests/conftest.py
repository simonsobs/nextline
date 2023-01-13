from __future__ import annotations

import atexit
import sys
import threading
from concurrent.futures.process import _python_exit
from typing import Any, Callable, List
from unittest.mock import Mock

import pytest


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
    from nextline.process import run

    mock_instance = Mock()
    mock_instance.return_value = None
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr(run, "Trace", mock_class)
    yield mock_class


@pytest.fixture(scope="session", autouse=True)
def wrap_futures_process_python_exit():
    """Catch error at exit in Python 3.8

    https://stackoverflow.com/q/68091084/7309855
    """
    yield
    if sys.version_info >= (3, 9):
        return

    if not _atexit_is_registered(_python_exit):
        return

    atexit.unregister(_python_exit)
    atexit.register(_wrap_python_exit)


def _wrap_python_exit(*args, **kwargs):
    try:
        _python_exit(*args, **kwargs)
    except OSError:
        pass


def _atexit_is_registered(func: Callable[..., Any]) -> bool:
    return func in _atexit_registered()


def _atexit_registered() -> List[Callable[..., Any]]:
    # https://stackoverflow.com/a/63813607/7309855
    import atexit

    ret = []

    class Capture:
        def __eq__(self, other):
            ret.append(other)
            return False

        def __call__(self):
            pass

    c = Capture()
    atexit.unregister(c)
    return ret
