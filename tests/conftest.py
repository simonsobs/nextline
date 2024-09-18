import sys
import threading
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def recover_trace() -> Iterator[None]:
    """Set the original trace function back after each test"""
    org_threading = threading.gettrace()
    org_sys = sys.gettrace()
    yield
    sys.settrace(org_sys)
    threading.settrace(org_threading)  # type: ignore
