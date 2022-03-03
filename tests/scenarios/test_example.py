import asyncio
from pathlib import Path
from typing import Set

import pytest

from nextline import Nextline
from nextline.utils import agen_with_wait

##__________________________________________________________________||
statement = """
import time
time.sleep(0.001)

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
async def monitor_state(nextline: Nextline):
    async for s in nextline.subscribe_state():
        # print("monitor_state()", s)
        pass


async def control_execution(nextline: Nextline):
    prev_ids: Set[int] = set()
    agen = agen_with_wait(nextline.subscribe_trace_ids())
    async for ids_ in agen:
        ids = set(ids_)
        new_ids, prev_ids = ids - prev_ids, ids

        tasks = {
            asyncio.create_task(control_trace(nextline, id_))
            for id_ in new_ids
        }
        _, pending = await agen.asend(tasks)

    await asyncio.gather(*pending)


async def control_trace(nextline: Nextline, trace_id):
    to_step = ["script_threading.run()", "script_asyncio.run()"]
    # print(f"control_trace({trace_id})")
    file_name = ""
    async for s in nextline.subscribe_trace_state(trace_id):
        # print(s)
        if not file_name == s["file_name"]:
            file_name = s["file_name"]
            assert nextline.get_source(file_name)
        if s["prompting"]:
            command = "next"
            if s["trace_event"] == "line":
                line = nextline.get_source_line(
                    line_no=s["line_no"], file_name=s["file_name"]
                )
                if line in to_step:
                    # print(line)
                    command = "step"
            nextline.send_pdb_command(trace_id, command)


async def run(nextline: Nextline):
    await asyncio.sleep(0.01)
    nextline.run()
    await nextline.finish()
    nextline.exception()
    nextline.result()  # raise exception
    await nextline.close()


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_run():

    nextline = Nextline(statement)

    assert nextline.state == "initialized"

    task_monitor_state = asyncio.create_task(monitor_state(nextline))

    task_control_execution = asyncio.create_task(control_execution(nextline))

    task_run = asyncio.create_task(run(nextline))

    aws = [task_run, task_monitor_state, task_control_execution]
    await asyncio.gather(*aws)

    assert nextline.state == "closed"


##__________________________________________________________________||
