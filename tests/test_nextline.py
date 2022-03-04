import asyncio

import pytest
from unittest.mock import Mock

from nextline import Nextline
from nextline.registry import PdbCIRegistry

# TODO: Simplify the tests in this module. The module is nearly identical to
# test_machine.py, which was created based on this module when the class Machine
# was extracted from the class Nextline.

# __________________________________________________________________||
SOURCE = """
import time
time.sleep(0.1)
""".strip()

SOURCE_TWO = """
x = 2
""".strip()

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()


# __________________________________________________________________||
@pytest.fixture(autouse=True)
def monkey_patch_trace(monkeypatch):
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_instance.pdb_ci_registry = Mock(spec=PdbCIRegistry)
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr("nextline.state.Trace", mock_class)
    yield mock_class


# __________________________________________________________________||
@pytest.mark.asyncio
async def test_repr():
    nextline = Nextline(SOURCE)
    repr(nextline)


@pytest.mark.asyncio
async def test_state_transitions_single_op():

    nextline = Nextline(SOURCE)
    event_initialized = asyncio.Event()
    task_monitor_state = asyncio.create_task(
        monitor_state(nextline, event_initialized)
    )
    await event_initialized.wait()

    nextline.run()

    await nextline.finish()
    await nextline.close()

    aws = [task_monitor_state]
    results = await asyncio.gather(*aws)

    states, *_ = results

    expectecd = ["initialized", "running", "exited", "finished", "closed"]
    assert expectecd == states


@pytest.mark.asyncio
async def test_state_transitions_multiple_async_ops():
    """test state transitions with multiple asynchronous operations

    The method finish() can be called multiple times asynchronously.
    However, the state transition should occur once.

    """

    nextline = Nextline(SOURCE)

    event_initialized = asyncio.Event()
    task_monitor_state = asyncio.create_task(
        monitor_state(nextline, event_initialized)
    )
    await event_initialized.wait()

    nextline.run()

    tasks_finish_and_close = asyncio.create_task(finish_and_close(nextline))

    aws = [task_monitor_state, tasks_finish_and_close]
    results = await asyncio.gather(*aws)

    states, *_ = results

    expectecd = ["initialized", "running", "exited", "finished", "closed"]
    assert expectecd == states


async def finish_and_close(nextline):
    nclients = 3
    await asyncio.gather(*[nextline.finish() for _ in range(nclients)])
    await nextline.close()


async def monitor_state(nextline, event_initialized):
    ret = []
    async for s in nextline.subscribe_state():
        if s == "initialized":
            event_initialized.set()
        # print('monitor_state()', s)
        ret.append(s)
    return ret


# __________________________________________________________________||
@pytest.mark.asyncio
async def test_reset():
    nextline = Nextline(SOURCE)
    nextline.run()
    await nextline.finish()
    nextline.reset()
    nextline.run()
    await nextline.finish()
    await nextline.close()


@pytest.mark.asyncio
async def test_reset_with_statement():
    nextline = Nextline(SOURCE)
    assert SOURCE.split("\n") == nextline.get_source()
    nextline.run()
    await nextline.finish()
    nextline.reset(statement=SOURCE_TWO)
    assert SOURCE_TWO.split("\n") == nextline.get_source()
    nextline.run()
    await nextline.finish()
    await nextline.close()


# __________________________________________________________________||
