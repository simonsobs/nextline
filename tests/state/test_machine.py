"""Test the class Machine

TODO: add a test for the method send_pdb_command()

"""
import asyncio
import pytest

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
async def test_init():
    with Machine(SOURCE) as obj:
        assert "initialized" == obj.state_name
        assert isinstance(obj.registry, SubscribableDict)
        assert SOURCE == obj.registry.get("statement")
        assert "<string>" == obj.registry.get("script_file_name")


@pytest.mark.asyncio
async def test_repr():
    with Machine(SOURCE) as obj:
        repr(obj)


@pytest.mark.asyncio
async def test_state_name_unknown(monkeypatch):
    with Machine(SOURCE) as obj:
        with monkeypatch.context() as m:
            m.setattr(obj, "_state", None)
            assert "unknown" == obj.state_name
            del obj._state
            assert "unknown" == obj.state_name


@pytest.mark.asyncio
async def test_transitions():
    async def subscribe():
        return [y async for y in registry.subscribe("state_name")]

    with Machine(SOURCE) as obj:
        registry = obj.registry
        t = asyncio.create_task(subscribe())
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
        await obj.close()
        assert "closed" == obj.state_name
        expected = [
            "initialized",
            "running",
            "finished",
            "initialized",
            "closed",
        ]
        assert expected == await t


@pytest.mark.asyncio
async def test_reset_with_statement():
    async def subscribe():
        return [y async for y in registry.subscribe("state_name")]

    with Machine(SOURCE) as obj:
        registry = obj.registry
        t = asyncio.create_task(subscribe())
        await asyncio.sleep(0)
        assert SOURCE == obj.registry.get("statement")
        await obj.run()
        await obj.finish()
        obj.reset(statement=SOURCE_TWO)
        assert SOURCE_TWO == obj.registry.get("statement")
        await obj.run()
        await obj.finish()
        await obj.close()
        expected = [
            "initialized",
            "running",
            "finished",
            "initialized",
            "running",
            "finished",
            "closed",
        ]
        assert expected == await t


@pytest.fixture(autouse=True)
def monkey_patch_run(monkey_patch_run):
    yield monkey_patch_run
