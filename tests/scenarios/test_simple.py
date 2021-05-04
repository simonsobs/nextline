import asyncio
import time

import pytest

from nextline import Nextline

##__________________________________________________________________||
statement = """
import time
time.sleep(0.01)
"""

breaks = {
    Nextline.__module__: ['<module>'],
}

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_run():

    nextline = Nextline(statement, breaks)
    assert nextline.global_state == 'initialized'

    nextline.run()

    async for global_state in nextline.subscribe_global_state():
        print(global_state)
        if global_state == 'running':
            break

    async for thread_asynctask_ids in nextline.subscribe_thread_asynctask_ids():
        print(thread_asynctask_ids)
        if thread_asynctask_ids:
            thread_asynctask_id = thread_asynctask_ids[0]
            break

    nextline.send_pdb_command(thread_asynctask_id, 'continue')
    await nextline.wait()
    assert nextline.global_state == 'finished'

##__________________________________________________________________||
