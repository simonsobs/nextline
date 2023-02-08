from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import NoReturn

import pytest

from nextline.utils import ExecutorFactory, run_in_process


class MockError(Exception):
    pass


def func() -> str:
    return "foo"


def func_raise() -> NoReturn:
    raise MockError()


async def test_one(executor_factory: ExecutorFactory) -> None:
    r = await run_in_process(executor_factory, func)
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_default_executor() -> None:
    r = await run_in_process(None, func)
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_repr(executor_factory: ExecutorFactory) -> None:
    r = await run_in_process(executor_factory, func)
    repr(r)
    await r


async def test_error(executor_factory: ExecutorFactory) -> None:
    r = await run_in_process(executor_factory, func_raise)
    with pytest.raises(MockError):
        await r
    assert r._process
    assert r._process.exitcode == 0


@pytest.fixture
def executor_factory() -> ExecutorFactory:
    return partial(ProcessPoolExecutor, max_workers=1)
