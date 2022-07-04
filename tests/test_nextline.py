from __future__ import annotations

import asyncio

import pytest
from unittest.mock import Mock

from nextline import Nextline
from nextline.state import Machine


SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


async def test_one(machine: Machine) -> None:
    del machine
    async with Nextline(SOURCE) as nextline:
        task = asyncio.create_task(nextline.run())
        nextline.send_pdb_command("continue", 1, 1)
        await task
        nextline.exception()
        await nextline.reset()
        await nextline.reset(statement=SOURCE_TWO, run_no_start_from=5)
        await nextline.run()


async def test_repr(machine):
    del machine
    async with Nextline(SOURCE) as nextline:
        assert repr(nextline)


@pytest.fixture
async def machine(monkeypatch):
    instance = Mock(spec=Machine)
    class_ = Mock(return_value=instance)
    monkeypatch.setattr("nextline.main.Machine", class_)
    return instance
