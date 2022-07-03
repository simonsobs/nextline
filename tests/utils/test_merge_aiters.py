from __future__ import annotations
from operator import itemgetter
from itertools import groupby


from nextline.utils import merge_aiters
from .aiterable import aiterable


async def test_one() -> None:
    obj = merge_aiters(aiterable(range(5)), aiterable([True, False] * 3))
    results = [i async for i in obj]
    actual = {
        k: list(map(itemgetter(1), v))
        for k, v in groupby(sorted(results, key=itemgetter(0)), itemgetter(0))
    }
    expected = {0: [0, 1, 2, 3, 4], 1: [True, False, True, False, True, False]}
    assert actual == expected
