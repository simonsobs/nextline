import pytest

from nextline.registry import PdbCIRegistry
from nextline.utils import Registry


def test_monkey_patch_trace(monkey_patch_trace):
    MockTrace = monkey_patch_trace
    trace = MockTrace()
    assert trace() is None
    assert isinstance(trace.pdb_ci_registry, PdbCIRegistry)


@pytest.mark.asyncio
async def test_wrap_registry(wrap_registry):
    MockRegistry = wrap_registry
    registry = MockRegistry()
    assert isinstance(registry, Registry)
    assert registry is not MockRegistry()  # new instance
