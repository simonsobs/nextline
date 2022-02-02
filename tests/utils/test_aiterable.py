import pytest

from .aiterable import aiterable


@pytest.mark.asyncio
async def test_aiterable():
    assert list(range(10)) == [i async for i in aiterable(range(10))]
