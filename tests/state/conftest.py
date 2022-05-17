import pytest


@pytest.fixture(autouse=True)
def monkey_patch_trace(monkey_patch_trace):
    yield monkey_patch_trace
