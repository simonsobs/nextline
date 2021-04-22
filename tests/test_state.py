import copy
import pytest
from unittest.mock import Mock, call, sentinel

from nextline.trace import State

##__________________________________________________________________||
def test_warning():
    state = State()
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

def test_nthreads():

    state = State()

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

def test_state(snapshot):

    state = State()

    id1 = (1111111, None)
    id2 = (1111111, 123)
    id3 = (2222222, None)
    id4 = (2222222, 124)

    state.update_started(id1)
    state.update_started(id2)

    snapshot.assert_match(state.data)

    state.update_prompting(id1)

    snapshot.assert_match(state.data)

    state.update_not_prompting(id1)

    snapshot.assert_match(state.data)

    state.update_prompting(id2)

    snapshot.assert_match(state.data)
    state.update_not_prompting(id2)

    snapshot.assert_match(state.data)

    state.update_started(id3)
    state.update_started(id4)

    state.update_prompting(id1)
    state.update_prompting(id3)

    snapshot.assert_match(state.data)

    state.update_not_prompting(id1)
    state.update_prompting(id2)
    state.update_not_prompting(id2)

    snapshot.assert_match(state.data)

    state.update_not_prompting(id3)
    state.update_prompting(id4)
    state.update_not_prompting(id4)

    snapshot.assert_match(state.data)

    state.update_finishing(id2)
    state.update_finishing(id4)
    state.update_finishing(id3)
    state.update_finishing(id1)

    snapshot.assert_match(state.data)

##__________________________________________________________________||
