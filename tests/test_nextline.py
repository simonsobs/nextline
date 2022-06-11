from __future__ import annotations

import asyncio

import pytest
from unittest.mock import Mock

from nextline import Nextline
from nextline.state import Machine
from nextline.utils import SubscribableDict


SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


@pytest.mark.asyncio
async def test_one(machine: Machine) -> None:
    del machine
    nextline = Nextline(SOURCE)
    task = asyncio.create_task(nextline.run())
    nextline.send_pdb_command(1, "continue")
    await task
    nextline.exception()
    nextline.reset()
    nextline.reset(statement=SOURCE_TWO, run_no_start_from=5)
    await nextline.run()
    await nextline.close()


def test_repr(machine):
    del machine
    nextline = Nextline(SOURCE)
    assert repr(nextline)


@pytest.fixture
async def machine(monkeypatch):
    spec_set = Machine("")
    await spec_set.close()
    instance = Mock(spec_set=spec_set)
    instance.registry = Mock(spec=SubscribableDict)
    class_ = Mock(return_value=instance)
    monkeypatch.setattr("nextline.main.Machine", class_)
    return instance
