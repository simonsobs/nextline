import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from nextline import InitOptions, Nextline

SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


def test_init_sync():
    '''Assert the init without the running loop.'''
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    init_options = InitOptions(statement=SOURCE)
    nextline = Nextline(init_options=init_options)
    assert nextline


async def test_repr() -> None:
    init_options = InitOptions(statement=SOURCE)
    nextline = Nextline(init_options=init_options)
    assert repr(nextline)
    async with nextline:
        assert repr(nextline)
    assert repr(nextline)


async def test_one() -> None:
    init_options = InitOptions(statement=SOURCE)
    async with Nextline(init_options=init_options) as nextline:
        async with nextline.run_session():
            async for prompt in nextline.prompts():
                await nextline.send_pdb_command(
                    'continue', prompt.prompt_no, prompt.trace_no
                )
        nextline.exception()
        await nextline.reset()
        await nextline.reset(statement=SOURCE_TWO, run_no_start_from=5)
        async with nextline.run_session():
            async for prompt in nextline.prompts():
                await nextline.send_pdb_command(
                    'continue', prompt.prompt_no, prompt.trace_no
                )


async def test_timeout(machine: Mock):
    async def close():
        await asyncio.sleep(5)

    machine.close.side_effect = close
    init_options = InitOptions(statement=SOURCE, timeout_on_exit=0.01)
    with pytest.raises(asyncio.TimeoutError):
        async with Nextline(init_options=init_options):
            pass


@pytest.fixture
async def machine(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    from nextline import main

    # instance = AsyncMock(spec=Model)
    instance = AsyncMock()
    instance.exception = Mock()
    class_ = Mock(return_value=instance)
    monkeypatch.setattr(main, 'Machine', class_)
    return instance


@pytest.fixture(autouse=True)
async def mock_continuous(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    from nextline import main

    # instance = AsyncMock(spec=Model)
    instance = AsyncMock()
    instance.exception = Mock()
    class_ = Mock(return_value=instance)
    monkeypatch.setattr(main, 'Continuous', class_)
    return instance
