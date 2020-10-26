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
    await nextline.wait()

##__________________________________________________________________||
