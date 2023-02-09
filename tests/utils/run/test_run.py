from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
from typing import NoReturn

import pytest

from nextline.utils import ExecutorFactory, run_in_process


def func_str() -> str:
    return 'foo'


async def test_success(executor_factory: ExecutorFactory) -> None:
    r = await run_in_process(func_str, executor_factory)
    assert 'foo' == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_default_executor() -> None:
    r = await run_in_process(func_str)
    assert 'foo' == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_thread_executor() -> None:
    r = await run_in_process(func_str, ThreadPoolExecutor)
    assert r._process is None

    # Signals are ignored
    r.interrupt()
    r.terminate()
    r.kill()

    assert 'foo' == await r


async def test_repr(executor_factory: ExecutorFactory) -> None:
    r = await run_in_process(func_str, executor_factory)
    repr(r)
    await r


#
class MockError(Exception):
    pass


def func_raise() -> NoReturn:
    raise MockError()


async def test_error(executor_factory: ExecutorFactory) -> None:
    r = await run_in_process(func_raise, executor_factory)
    with pytest.raises(MockError):
        await r
    assert r._process
    assert r._process.exitcode == 0


@pytest.fixture
def executor_factory() -> ExecutorFactory:
    return partial(ProcessPoolExecutor, max_workers=1)
