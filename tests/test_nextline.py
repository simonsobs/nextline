import asyncio

import pytest
from unittest.mock import Mock

from nextline import Nextline


SOURCE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()


@pytest.fixture(autouse=True)
def monkey_patch_trace(monkeypatch):
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr("nextline.run.Trace", mock_class)
    yield mock_class


def test_repr():
    nextline = Nextline(SOURCE)
    repr(nextline)


def test_statement():
    nextline = Nextline(SOURCE)
    assert SOURCE == nextline.statement


@pytest.mark.asyncio
async def test_states():
    async def initialized(nextline: Nextline):
        async for s in nextline.subscribe_state():
            if s == "initialized":
                await asyncio.sleep(0)
                break

    async def subscribe_state(nextline: Nextline):
        return [s async for s in nextline.subscribe_state()]

    nextline = Nextline(SOURCE)
    task_monitor_state = asyncio.create_task(subscribe_state(nextline))

    await initialized(nextline)

    await nextline.run()

    await nextline.close()

    states = await task_monitor_state

    expected = ["initialized", "running", "exited", "finished", "closed"]
    assert expected == states


@pytest.mark.asyncio
async def test_raise():
    nextline = Nextline(SOURCE_RAISE)
    await nextline.run()
    with pytest.raises(Exception) as exc:
        nextline.result()
    assert ("foo", "bar") == exc.value.args
    assert ("foo", "bar") == nextline.exception().args
    await nextline.close()


@pytest.mark.asyncio
async def test_reset():
    nextline = Nextline(SOURCE)
    await nextline.run()
    nextline.reset()
    await nextline.run()
    await nextline.close()


@pytest.mark.asyncio
async def test_reset_with_statement():
    nextline = Nextline(SOURCE)
    assert SOURCE.split("\n") == nextline.get_source()
    await nextline.run()
    nextline.reset(statement=SOURCE_TWO)
    assert SOURCE_TWO.split("\n") == nextline.get_source()
    await nextline.run()
    await nextline.close()
