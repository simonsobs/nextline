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
async def test_state():

    nextline = Nextline(SOURCE)
    task_monitor_state = asyncio.create_task(monitor_state(nextline))
    nextline.run()
    await nextline.wait()
    await nextline.close()
    aws = [task_monitor_state]
    results = await asyncio.gather(*aws)
    states, *_ = results
    assert ['initialized', 'running', 'exited', 'finished', 'closed'] == states

async def monitor_state(nextline):
    ret = []
    async for s in nextline.subscribe_global_state():
        # print('monitor_state()', s)
        ret.append(s)
    return ret

##__________________________________________________________________||
