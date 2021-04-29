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

    global_state_subscription = nextline.subscribe_global_state()
    global_state = await global_state_subscription.__anext__()
    assert global_state == 'initialized'

    assert nextline.global_state == 'initialized'

    nextline.run()

    global_state = await global_state_subscription.__anext__()
    assert global_state == 'running'

    assert nextline.global_state == 'running'

    thread_asynctask_ids_subscription = nextline.subscribe_thread_asynctask_ids()
    thread_asynctask_ids = await thread_asynctask_ids_subscription.__anext__()
    thread_asynctask_id = thread_asynctask_ids[0]

    thread_asynctask_state_subscription = nextline.subscribe_thread_asynctask_state(thread_asynctask_id)
    thread_asynctask_state = await thread_asynctask_state_subscription.__anext__()

    pdb_ci = nextline.pdb_ci_registry.get_ci(thread_asynctask_id)
    pdb_ci.send_pdb_command('continue')
    await nextline.wait()
    assert nextline.global_state == 'finished'

##__________________________________________________________________||
