import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from nextline import Nextline

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
    nextline = Nextline(SOURCE)
    assert nextline


async def test_repr():
    nextline = Nextline(SOURCE)
    assert repr(nextline)
    async with nextline:
        assert repr(nextline)
    assert repr(nextline)


async def test_one() -> None:
    async with Nextline(SOURCE) as nextline:
        task = asyncio.create_task(nextline.run())
        print(task)
        async for prompt_info in nextline.subscribe_prompt_info():
            if not prompt_info.open:
                continue
            nextline.send_pdb_command("continue", 1, 1)
            break
        await task
        nextline.exception()
        await nextline.reset()
        await nextline.reset(statement=SOURCE_TWO, run_no_start_from=5)
        task = asyncio.create_task(nextline.run())
        async for prompt_info in nextline.subscribe_prompt_info():
            if not prompt_info.open:
                continue
            nextline.send_pdb_command("continue", 1, 1)
            break
        await task


async def test_timeout(machine: Mock):
    async def close():
        await asyncio.sleep(5)

    machine.close.side_effect = close
    with pytest.raises(asyncio.TimeoutError):
        async with Nextline(SOURCE, timeout_on_exit=0.01):
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
