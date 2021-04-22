import asyncio
import time

import pytest

from nextline import Nextline, ThreadSafeAsyncioEvent

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
async def test_simple():
    event = ThreadSafeAsyncioEvent()
    nextline = Nextline(statement, breaks, event=event)
    assert nextline.status == 'initialized'
    nextline.run()
    await event.wait()
    time.sleep(0.02) # wait because sometimes pdb_ci is not in the registry yet
    state = nextline.state.data
    thread_id = list(state.keys())[0]
    task_id = list(state[thread_id].keys())[0]
    pdb_ci = nextline.pdb_ci_registry.get_ci((thread_id, task_id))
    pdb_ci.send_pdb_command('continue')
    await nextline.wait()
    assert nextline.status == 'finished'

##__________________________________________________________________||
