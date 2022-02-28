import asyncio
from pathlib import Path

import pytest

from nextline import Nextline

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
        print("monitor_state()", s)


async def control_execution(nextline: Nextline):
    prev_ids = set()
    tasks = set()

    # The lines of code between ============= can be rewritten with
    # one line of code as
    #   async for ids in nextline.subscribe_trace_ids():
    # if exceptions occurred in tasks don't need to be re-raised.

    # ==================================================
    subscription = nextline.subscribe_trace_ids()
    task_anext = asyncio.create_task(subscription.__anext__())
    while True:
        aws = {task_anext, *tasks}
        done, pending = await asyncio.wait(
            aws, return_when=asyncio.FIRST_COMPLETED
        )
        results = [  # noqa: F841
            t.result() for t in tasks if t in done
        ]  # re-raise exception
        tasks = tasks & pending
        if not task_anext.done():
            continue
        try:
            ids = task_anext.result()
        except StopAsyncIteration:
            break
        task_anext = asyncio.create_task(subscription.__anext__())
        # ===============================================

        ids = set(ids)

        new_ids = ids - prev_ids

        for id_ in new_ids:
            task = asyncio.create_task(control_thread_task(nextline, id_))
            tasks.add(task)

        prev_ids = ids


async def control_thread_task(nextline: Nextline, thread_task_id):
    to_step = ["script_threading.run()", "script_asyncio.run()"]
    print(f"control_thread_task({thread_task_id})")
    file_name = ""
    async for s in nextline.subscribe_trace_state(thread_task_id):
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
            nextline.send_pdb_command(thread_task_id, command)


async def run(nextline: Nextline):
    await asyncio.sleep(0.1)
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
