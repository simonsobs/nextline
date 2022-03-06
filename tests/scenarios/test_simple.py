import asyncio
import pytest

from nextline import Nextline

statement = """
import time

time.sleep(0.01)
"""


@pytest.mark.asyncio
async def test_run():

    nextline = Nextline(statement)
    assert nextline.state == "initialized"

    run = asyncio.create_task(nextline.run())

    await asyncio.sleep(0.01)

    async for state in nextline.subscribe_state():
        if state == "running":
            break

    async for trace_ids in nextline.subscribe_trace_ids():
        if trace_ids:
            trace_id = trace_ids[0]
            break

    n_prompting = 0
    async for state in nextline.subscribe_prompting(trace_id):
        if state.prompting:
            n_prompting += 1
            nextline.send_pdb_command(trace_id, "next")
    assert 3 == n_prompting

    await run
    assert nextline.state == "finished"
    await nextline.close()
    assert nextline.state == "closed"
