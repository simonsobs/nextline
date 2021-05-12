import sys
import threading
import asyncio
import copy
import pytest
from unittest.mock import Mock, call, sentinel

from nextline.registry import Registry

##__________________________________________________________________||
pytestmark = pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_warning():
    registry = Registry()
    await asyncio.to_thread(_test_warning, registry)

def _test_warning(registry):
    id1 = (1111111, None)
    registry.update_finishing(id1)
    with pytest.warns(UserWarning) as record:
        registry.update_finishing(id1)
    assert "not found: thread_asynctask_id" in (record[0].message.args[0])
    id2 = (1111111, 123)
    registry.update_finishing(id2)
    with pytest.warns(UserWarning) as record:
        registry.update_finishing(id2)
    assert "not found: thread_asynctask_id" in (record[0].message.args[0])

##__________________________________________________________________||
