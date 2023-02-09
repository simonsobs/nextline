from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import NoReturn

import pytest

from nextline.utils import ExecutorFactory, run_in_process


def func_str() -> str:
    return 'foo'


async def test_success(executor_factory: ExecutorFactory) -> None:
    running = await run_in_process(func_str, executor_factory)
    result = await running
    assert running._process
    assert running._process.exitcode == 0
    assert 'foo' == result.returned


async def test_default_executor() -> None:
    running = await run_in_process(func_str)
    result = await running
    assert running._process
    assert running._process.exitcode == 0
    assert 'foo' == result.returned


async def test_repr(executor_factory: ExecutorFactory) -> None:
    running = await run_in_process(func_str, executor_factory)
    repr(running)
    await running


#
class MockError(Exception):
    pass


def func_raise() -> NoReturn:
    raise MockError()


async def test_error(executor_factory: ExecutorFactory) -> None:
    running = await run_in_process(func_raise, executor_factory)
    result = await running
    assert running._process
    assert running._process.exitcode == 0
    assert isinstance(result.raised, MockError)


@pytest.fixture
def executor_factory() -> ExecutorFactory:
    return partial(ProcessPoolExecutor, max_workers=1)
