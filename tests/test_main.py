import asyncio

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
async def test_simple():
    nextline = Nextline(statement, breaks)
    nextline.run()
    while True:
        with nextline.condition:
            if nextline.control.local_queue_dict:
                break
        await asyncio.sleep(0.01)
    print(nextline.control.local_queue_dict)
    await nextline.wait()

##__________________________________________________________________||
