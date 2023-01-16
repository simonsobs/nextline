import asyncio
from unittest.mock import Mock

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


def test_init_sync(machine: Mock):
    '''Assert the init without the running loop.'''
    del machine
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
    nextline = Nextline(SOURCE)
    assert nextline


async def test_one(machine: Mock) -> None:
    del machine
    async with Nextline(SOURCE) as nextline:
        task = asyncio.create_task(nextline.run())
        nextline.send_pdb_command("continue", 1, 1)
        await task
        nextline.exception()
        await nextline.reset()
        await nextline.reset(statement=SOURCE_TWO, run_no_start_from=5)
        await nextline.run()


async def test_repr(machine: Mock):
    del machine
    async with Nextline(SOURCE) as nextline:
        assert repr(nextline)


@pytest.fixture
async def machine(monkeypatch: pytest.MonkeyPatch) -> Mock:
    from nextline import main

    instance = Mock(spec=Machine)
    class_ = Mock(return_value=instance)
    monkeypatch.setattr(main, "Machine", class_)
    return instance
