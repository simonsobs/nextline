import sys
import threading
import asyncio
import copy
import pytest
from unittest.mock import Mock, call, sentinel

from nextline.trace import State

##__________________________________________________________________||
pytestmark = pytest.mark.skipif(sys.version_info < (3, 9), reason="asyncio.to_thread()")

##__________________________________________________________________||
@pytest.mark.asyncio
async def test_warning():
    state = State()
    await asyncio.to_thread(_test_warning, state)

def _test_warning(state):
    id1 = (1111111, None)
    state.update_finishing(id1)
    with pytest.warns(UserWarning) as record:
        state.update_finishing(id1)
    assert "not found: thread_asynctask_id" in (record[0].message.args[0])
    id2 = (1111111, 123)
    state.update_finishing(id2)
    with pytest.warns(UserWarning) as record:
        state.update_finishing(id2)
    assert "not found: thread_asynctask_id" in (record[0].message.args[0])

@pytest.mark.asyncio
async def test_nthreads():
    state = State()
    await asyncio.to_thread(_test_nthreads, state)

def _test_nthreads(state):

    id1 = (1111111, None)
    id2 = (1111111, 123)
    id3 = (2222222, None)
    id4 = (2222222, 124)

    assert 0 == state.nthreads
    state.update_started(id1)
    assert 1 == state.nthreads
    state.update_started(id2)
    assert 1 == state.nthreads
    state.update_started(id3)
    assert 2 == state.nthreads
    state.update_started(id4)
    assert 2 == state.nthreads
    state.update_finishing(id2)
    assert 2 == state.nthreads
    state.update_finishing(id4)
    assert 2 == state.nthreads
    state.update_finishing(id3)
    assert 1 == state.nthreads
    state.update_finishing(id1)
    assert 0 == state.nthreads

##__________________________________________________________________||
