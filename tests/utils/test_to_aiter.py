from nextline.utils import aiterable, to_aiter


async def test_to_aiter():
    assert list(range(10)) == [i async for i in to_aiter(range(10))]


async def test_aiterable():
    assert list(range(10)) == [i async for i in aiterable(range(10))]
