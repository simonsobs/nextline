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


@pytest.mark.asyncio
async def test_init():
    async with Machine(Mock()) as obj:
        assert "initialized" == obj.state_name


@pytest.mark.asyncio
async def test_repr():
    async with Machine(Mock()) as obj:
        repr(obj)


@pytest.mark.asyncio
async def test_state_name_unknown(monkeypatch):
    async with Machine(Mock()) as obj:
        with monkeypatch.context() as m:
            m.setattr(obj, "_state", None)
            assert "unknown" == obj.state_name
            del obj._state
            assert "unknown" == obj.state_name


@pytest.mark.asyncio
async def test_transitions():
    context = Mock(spec=Context)
    context.exception = None

    async with Machine(context) as obj:
        await asyncio.sleep(0)
        assert "initialized" == obj.state_name
        await obj.run()
        assert "running" == obj.state_name
        await obj.finish()
        assert "finished" == obj.state_name
        obj.result()
        obj.exception()
        obj.reset()
        assert "initialized" == obj.state_name
    assert "closed" == obj.state_name


@pytest.mark.asyncio
async def test_reset_with_statement():
    context = Mock(spec=Context)
    context.exception = None

    async with Machine(context) as obj:
        await asyncio.sleep(0)
        await obj.run()
        await obj.finish()
        obj.reset(statement=SOURCE_TWO)
        await obj.run()
        await obj.finish()
