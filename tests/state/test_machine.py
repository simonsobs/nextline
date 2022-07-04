"""Test the class Machine

"""

import asyncio
from unittest.mock import Mock
import pytest

from nextline.context import Context
from nextline.state import Machine


SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


async def test_init(context: Context):
    async with Machine(context) as obj:
        assert "initialized" == obj.state_name


async def test_repr(context: Context):
    async with Machine(context) as obj:
        repr(obj)


async def test_state_name_unknown(monkeypatch, context: Context):
    async with Machine(context) as obj:
        with monkeypatch.context() as m:
            m.setattr(obj, "_state", None)
            assert "unknown" == obj.state_name
            del obj._state
            assert "unknown" == obj.state_name


async def test_transitions(context: Context):
    async with Machine(context) as obj:
        await asyncio.sleep(0)
        assert "initialized" == obj.state_name
        await obj.run()
        assert "running" == obj.state_name
        await obj.finish()
        assert "finished" == obj.state_name
        obj.result()
        obj.exception()
        await obj.reset()
        assert "initialized" == obj.state_name
    assert "closed" == obj.state_name


async def test_reset_with_statement(context: Context):
    async with Machine(context) as obj:
        await asyncio.sleep(0)
        await obj.run()
        await obj.finish()
        await obj.reset(statement=SOURCE_TWO)
        await obj.run()
        await obj.finish()


@pytest.fixture
def context() -> Mock:
    y = Mock(spec=Context)
    y.exception = None
    return y
