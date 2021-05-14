import asyncio

import pytest
from unittest.mock import Mock

from nextline import Nextline
from nextline.registry import PdbCIRegistry

##__________________________________________________________________||
SOURCE = """
import time
time.sleep(0.1)
""".strip()

SOURCE_RAISE = """
raise Exception('foo', 'bar')
""".strip()

##__________________________________________________________________||
@pytest.fixture(autouse=True)
def monkey_patch_trace(monkeypatch):
    mock_instance = Mock()
    mock_instance.return_value = None
    mock_instance.pdb_ci_registry = Mock(spec=PdbCIRegistry)
    mocak_class = Mock(return_value=mock_instance)
    monkeypatch.setattr('nextline.state.Trace', mocak_class)
    yield mocak_class

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_repr():
    nextline = Nextline(SOURCE)
    repr(nextline)

@pytest.mark.asyncio
async def test_state_transitions_single_op():

    nextline = Nextline(SOURCE)
    event_initialized = asyncio.Event()
    task_monitor_state = asyncio.create_task(monitor_state(nextline, event_initialized))
    await event_initialized.wait()

    nextline.run()

    await nextline.finish()
    await nextline.close()

    aws = [task_monitor_state]
    results = await asyncio.gather(*aws)

    states, *_ = results

    expectecd = ['initialized', 'running', 'exited', 'finished', 'closed']
    assert  expectecd == states

@pytest.mark.asyncio
async def test_state_transitions_multiple_async_ops():
    """test state transitions with multiple asynchronous operations

    The methods finish() and close() can be called multiple times
    asynchronously. However, each state transition should occur once.

    """

    nclients = 3

    nextline = Nextline(SOURCE)

    event_initialized = asyncio.Event()
    task_monitor_state = asyncio.create_task(monitor_state(nextline, event_initialized))
    await event_initialized.wait()

    nextline.run()

    tasks_finish_and_close = []
    for _ in range(nclients):
        task = asyncio.create_task(finish_and_close(nextline))
        tasks_finish_and_close.append(task)

    aws = [task_monitor_state, *tasks_finish_and_close]
    results = await asyncio.gather(*aws)

    states, *_ = results

    expectecd = ['initialized', 'running', 'exited', 'finished', 'closed']
    assert  expectecd == states

async def finish_and_close(nextline):
    await nextline.finish()
    await nextline.close()

async def monitor_state(nextline, event_initialized):
    ret = []
    async for s in nextline.subscribe_global_state():
        if s == 'initialized':
            event_initialized.set()
        # print('monitor_state()', s)
        ret.append(s)
    return ret

##__________________________________________________________________||
