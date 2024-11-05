import asyncio
from collections.abc import Awaitable, Callable
from inspect import iscoroutinefunction
from typing import NoReturn, TypeGuard, cast
from unittest.mock import Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nextline.utils import UntilNotNoneTimeout, until_true


def func_factory(
    counts: int, sync: bool = False
) -> Callable[[], bool] | Callable[[], Awaitable[bool]]:
    assert counts

    def func() -> bool:
        nonlocal counts
        counts -= 1
        return counts == 0

    async def afunc() -> bool:
        return func()

    return func if sync else afunc


def is_async_func(
    f: Callable[[], bool] | Callable[[], Awaitable[bool]],
) -> TypeGuard[Callable[[], Awaitable[bool]]]:
    return iscoroutinefunction(f)


@given(counts=st.integers(min_value=1, max_value=10))
def test_func_factory_sync(counts: int) -> None:
    func = func_factory(counts, sync=True)
    for _ in range(counts - 1):
        assert not func()
    assert func()


@given(counts=st.integers(min_value=1, max_value=10))
async def test_func_factory_async(counts: int) -> None:
    func = func_factory(counts, sync=False)
    assert is_async_func(func)
    for _ in range(counts - 1):
        assert not await func()
    assert await func()


@given(counts=st.integers(min_value=1, max_value=10), sync=st.booleans())
async def test_counts(counts: int, sync: bool) -> None:
    wrapped = func_factory(counts, sync=sync)
    func = Mock(wraps=wrapped)
    await until_true(func)
    assert func.call_count == counts


@given(sync=st.booleans())
async def test_timeout(sync: bool) -> None:
    counts = cast(int, float('inf'))
    assert counts == counts - 1
    wrapped = func_factory(counts, sync=sync)
    func = Mock(wraps=wrapped)
    with pytest.raises(UntilNotNoneTimeout):
        await until_true(func, timeout=0.001)


@pytest.mark.timeout(5)
async def test_timeout_never_return() -> None:
    async def func() -> NoReturn:
        while True:
            await asyncio.sleep(0)

    with pytest.raises(UntilNotNoneTimeout):
        await until_true(func, timeout=0.001)
