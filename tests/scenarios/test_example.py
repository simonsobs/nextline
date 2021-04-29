import sys
import threading
from pathlib import Path
import asyncio
import time

import pytest

from nextline import Nextline

##__________________________________________________________________||
statement = """
import time
time.sleep(0.3)

def f():
    for _ in range(1000):
        pass
    return

f()
f()

print('here!')

import scriptone
scriptone.run()

import scripttwo
scripttwo.run()
""".strip()

breaks = {
    Nextline.__module__: ['<module>'],
}

##__________________________________________________________________||
@pytest.fixture(autouse=True)
def monkey_patch_syspath(monkeypatch):
    this_dir = Path(__file__).resolve().parent
    monkeypatch.syspath_prepend(str(this_dir))
    yield

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_run():
    nextline = Nextline(statement, breaks)
    global_state_subscription = nextline.subscribe_global_state()
    global_state = await global_state_subscription.__anext__()
    assert global_state == 'initialized'
    assert nextline.global_state == 'initialized'
    thread_asynctask_ids_subscription = nextline.subscribe_thread_asynctask_ids()
    thread_asynctask_ids = await thread_asynctask_ids_subscription.__anext__()
    assert [] == thread_asynctask_ids
    nextline.run()
    thread_asynctask_ids = await thread_asynctask_ids_subscription.__anext__()
    print(thread_asynctask_ids)
    g = nextline.nextline_generator()
    nextline = await g.__anext__()
    time.sleep(0.02) # wait because sometimes pdb_ci is not in the registry yet
    global_state = await global_state_subscription.__anext__()
    assert global_state == 'running'
    assert nextline.global_state == 'running'
    state = nextline.state.data
    thread_id = list(state.keys())[0]
    task_id = list(state[thread_id].keys())[0]
    pdb_ci = nextline.pdb_ci_registry.get_ci((thread_id, task_id))
    pdb_ci.send_pdb_command('continue')
    # await nextline.wait()
    # assert nextline.global_state == 'finished'

##__________________________________________________________________||
