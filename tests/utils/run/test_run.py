from typing import NoReturn

from nextline.utils import run_in_process


def func_str() -> str:
    return 'foo'


async def test_success() -> None:
    running = await run_in_process(func_str)
    assert running.process
    assert running.process_created_at
    result = await running
    assert running.process.exitcode == 0
    assert 'foo' == result.returned


async def test_default_executor() -> None:
    running = await run_in_process(func_str)
    result = await running
    assert running.process
    assert running.process.exitcode == 0
    assert 'foo' == result.returned


async def test_repr() -> None:
    running = await run_in_process(func_str)
    repr(running)
    await running


#
class MockError(Exception):
    pass


def func_raise() -> NoReturn:
    raise MockError()


async def test_error() -> None:
    running = await run_in_process(func_raise)
    result = await running
    assert running.process
    assert running.process.exitcode == 0
    assert isinstance(result.raised, MockError)
