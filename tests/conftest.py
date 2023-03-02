import sys
import threading

import pytest


@pytest.fixture(autouse=True)
def recover_trace():
    """Set the original trace function back after each test"""
    trace_org = sys.gettrace()
    yield
    sys.settrace(trace_org)
    threading.settrace(trace_org)


if not sys.version_info >= (3, 9):
    from nextline.test import suppress_atexit_oserror

    _ = pytest.fixture(scope='session', autouse=True)(suppress_atexit_oserror)
