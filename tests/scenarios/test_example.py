import sys
import asyncio
import threading
from pathlib import Path
import asyncio
import time

import pytest

from nextline import Nextline

##__________________________________________________________________||
statement = """
import time
time.sleep(0.1)

def f():
    for _ in range(10):
        pass
    return

f()
f()

print('here!')

import script_threading
script_threading.run()

import script_asyncio
script_asyncio.run()
""".strip()

##__________________________________________________________________||
@pytest.fixture(autouse=True)
def monkey_patch_syspath(monkeypatch):
    this_dir = Path(__file__).resolve().parent
    monkeypatch.syspath_prepend(str(this_dir))
    yield

##__________________________________________________________________||
async def monitor_global_state(nextline):
    async for s in nextline.subscribe_global_state():
        print(s)

async def control_execution(nextline):
    controllers = {}
    async for ids in nextline.subscribe_thread_asynctask_ids():
        prev_ids = list(controllers.keys())
        new_ids = [id_ for id_ in ids if id_ not in prev_ids]
        ended_ids = [id_ for id_ in prev_ids if id_ not in ids]
        for id_ in new_ids:
            task = asyncio.create_task(control_thread_task(nextline, id_))
            controllers[id_] = task
        for id_ in ended_ids:
            del controllers[id_]

async def control_thread_task(nextline, thread_task_id):
    to_step = ['script_threading.run()', 'script_asyncio.run()']

    print(thread_task_id)
    async for s in nextline.subscribe_thread_asynctask_state(thread_task_id):
        print(s)
        if s['prompting']:
            command = 'next'
            if s['trace_event'] == 'line':
                line = nextline.get_source_line(line_no=s['line_no'], file_name=s['file_name'])
                if line in to_step:
                    print(line)
                    command = 'step'
            nextline.send_pdb_command(thread_task_id, command)


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_run():

    nextline = Nextline(statement)

    assert nextline.global_state == 'initialized'

    task_monitor_global_state = asyncio.create_task(monitor_global_state(nextline))
    # await asyncio.sleep(0)

    task_control_execution = asyncio.create_task(control_execution(nextline))

    nextline.run()

    await nextline.wait()
    assert nextline.global_state == 'finished'

##__________________________________________________________________||
