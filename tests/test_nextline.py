import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from nextline import Nextline
from nextline.state import Machine

SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


def test_init_sync(machine: AsyncMock):
    '''Assert the init without the running loop.'''
    del machine
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    nextline = Nextline(SOURCE)
    assert nextline


async def test_one(machine: AsyncMock) -> None:
    del machine
    async with Nextline(SOURCE) as nextline:
        task = asyncio.create_task(nextline.run())
        nextline.send_pdb_command("continue", 1, 1)
        await task
        nextline.exception()
        await nextline.reset()
        await nextline.reset(statement=SOURCE_TWO, run_no_start_from=5)
        await nextline.run()


async def test_repr(machine: AsyncMock):
    del machine
    async with Nextline(SOURCE) as nextline:
        assert repr(nextline)


@pytest.mark.skip(reason='it blocks')
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

    instance = AsyncMock(spec=Machine)
    class_ = Mock(return_value=instance)
    monkeypatch.setattr(main, "Machine", class_)
    return instance
