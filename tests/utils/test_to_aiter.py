import pytest

from nextline.utils import aiterable, to_aiter


@pytest.mark.parametrize('thread', [True, False])
async def test_to_aiter(thread: bool) -> None:
    assert list(range(10)) == [i async for i in to_aiter(range(10), thread=thread)]


async def test_aiterable() -> None:
    with pytest.deprecated_call():
        assert list(range(10)) == [i async for i in aiterable(range(10))]
