import asyncio
from pathlib import Path
from typing import Dict

import pytest

from nextline import Nextline

statement = """
import script
script.run()

""".strip()


@pytest.fixture(autouse=True)
def monkey_patch_syspath(monkeypatch):
    this_dir = Path(__file__).resolve().parent
    monkeypatch.syspath_prepend(str(this_dir))
    yield


async def monitor_state(nextline: Nextline):
    async for s in nextline.subscribe_state():
        # print(s)
        pass


async def control_execution(nextline: Nextline):
    controllers: Dict[int, asyncio.Task] = {}
    async for ids in nextline.subscribe_trace_ids():
        prev_ids = list(controllers.keys())
        new_ids = [id_ for id_ in ids if id_ not in prev_ids]
        ended_ids = [id_ for id_ in prev_ids if id_ not in ids]
        for id_ in new_ids:
            task = asyncio.create_task(control_trace(nextline, id_))
            controllers[id_] = task
        for id_ in ended_ids:
            del controllers[id_]


async def control_trace(nextline: Nextline, trace_id: int):
    # print(trace_id)
    async for s in nextline.subscribe_trace_state(trace_id):
        # print(s)
        if s["prompting"]:
            nextline.send_pdb_command(trace_id, "next")


@pytest.mark.asyncio
async def test_run():

    nextline = Nextline(statement)

    assert nextline.state == "initialized"

    task_monitor_state = asyncio.create_task(monitor_state(nextline))
    # await asyncio.sleep(0)

    task_control_execution = asyncio.create_task(control_execution(nextline))
    await asyncio.sleep(0.01)

    nextline.run()

    await nextline.finish()
    assert nextline.state == "finished"
    await nextline.close()
    assert nextline.state == "closed"
    await asyncio.gather(task_monitor_state, task_control_execution)
