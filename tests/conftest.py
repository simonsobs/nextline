import sys
import threading
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def recover_trace() -> Iterator[None]:
    """Set the original trace function back after each test"""
    trace_org = sys.gettrace()
    yield
    sys.settrace(trace_org)
    threading.settrace(trace_org)  # type: ignore
