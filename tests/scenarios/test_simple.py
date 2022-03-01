import asyncio
import pytest

from nextline import Nextline

##__________________________________________________________________||
statement = """
import time
time.sleep(0.01)
"""


##__________________________________________________________________||
@pytest.mark.asyncio
async def test_run():

    nextline = Nextline(statement)
    assert nextline.state == "initialized"

    nextline.run()

    await asyncio.sleep(0.01)

    async for state in nextline.subscribe_state():
        if state == "running":
            break

    async for trace_ids in nextline.subscribe_trace_ids():
        if trace_ids:
            trace_id = trace_ids[0]
            break

    async for state in nextline.subscribe_trace_state(trace_id):
        if state["prompting"]:
            break

    nextline.send_pdb_command(trace_id, "continue")
    await nextline.finish()
    assert nextline.state == "finished"
    await nextline.close()
    assert nextline.state == "closed"


##__________________________________________________________________||
