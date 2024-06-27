from itertools import groupby
from operator import itemgetter

from nextline.utils import merge_aiters, to_aiter


async def test_one() -> None:
    obj = merge_aiters(to_aiter(range(5)), to_aiter([True, False] * 3))
    results = [i async for i in obj]
    actual = {
        k: list(map(itemgetter(1), v))
        for k, v in groupby(sorted(results, key=itemgetter(0)), itemgetter(0))
    }
    expected = {0: [0, 1, 2, 3, 4], 1: [True, False, True, False, True, False]}
    assert actual == expected
