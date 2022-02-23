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

    async for state in nextline.subscribe_state():
        if state == "running":
            break

    async for thread_asynctask_ids in nextline.subscribe_thread_asynctask_ids():
        if thread_asynctask_ids:
            thread_asynctask_id = thread_asynctask_ids[0]
            break

    async for state in nextline.subscribe_thread_asynctask_state(
        thread_asynctask_id
    ):
        if state["prompting"]:
            break

    nextline.send_pdb_command(thread_asynctask_id, "continue")
    await nextline.finish()
    assert nextline.state == "finished"
    await nextline.close()
    assert nextline.state == "closed"


##__________________________________________________________________||
