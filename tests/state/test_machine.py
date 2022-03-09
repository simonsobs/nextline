"""Test the class Machine

TODO: add a test for the method send_pdb_command()

"""
import asyncio
import pytest

from nextline.state import Machine
from nextline.utils import SubscribableDict


# __________________________________________________________________||
SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()


# __________________________________________________________________||
@pytest.mark.asyncio
async def test_init():
    obj = Machine(SOURCE)
    assert "initialized" == obj.state_name
    assert isinstance(obj.registry, SubscribableDict)
    assert SOURCE == obj.registry.get("statement")
    assert "<string>" == obj.registry.get("script_file_name")


@pytest.mark.asyncio
async def test_repr():
    obj = Machine(SOURCE)
    repr(obj)


@pytest.mark.asyncio
async def test_state_name_unknown():
    obj = Machine(SOURCE)
    obj._state = None
    assert "unknown" == obj.state_name
    del obj._state
    assert "unknown" == obj.state_name


@pytest.mark.asyncio
async def test_transitions():
    async def subscribe():
        return [y async for y in registry.subscribe("state_name")]

    obj = Machine(SOURCE)
    registry = obj.registry
    t = asyncio.create_task(subscribe())
    await asyncio.sleep(0)
    assert "initialized" == obj.state_name
    obj.run()
    assert "running" == obj.state_name
    await obj.finish()
    assert "finished" == obj.state_name
    obj.result()
    obj.exception()
    obj.reset()
    assert "initialized" == obj.state_name
    await obj.close()
    assert "closed" == obj.state_name
    expected = [
        "initialized",
        "running",
        "exited",
        "finished",
        "initialized",
        "closed",
    ]
    assert expected == await t


@pytest.mark.asyncio
async def test_reset_with_statement():
    async def subscribe():
        return [y async for y in registry.subscribe("state_name")]

    obj = Machine(SOURCE)
    registry = obj.registry
    t = asyncio.create_task(subscribe())
    await asyncio.sleep(0)
    assert SOURCE == obj.registry.get("statement")
    obj.run()
    await obj.finish()
    obj.reset(statement=SOURCE_TWO)
    assert SOURCE_TWO == obj.registry.get("statement")
    obj.run()
    await obj.finish()
    await obj.close()
    expected = [
        "initialized",
        "running",
        "exited",
        "finished",
        "initialized",
        "running",
        "exited",
        "finished",
        "closed",
    ]
    assert expected == await t
