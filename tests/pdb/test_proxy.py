import sys

import pytest
from unittest.mock import Mock

from nextline.trace import State, compose_thread_asynctask_id
from nextline.pdb.proxy import PdbProxy
from nextline.pdb.custom import CustomizedPdb

##__________________________________________________________________||
@pytest.fixture()
def MockCustomizedPdb(monkeypatch):
    mock_instance = Mock(spec=CustomizedPdb)
    mock_instance.trace_dispatch.return_value = mock_instance.trace_dispatch
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr('nextline.pdb.proxy.CustomizedPdb', mock_class)
    yield mock_class

@pytest.fixture()
def mock_state():
    y = Mock(spec=State)
    yield y

##__________________________________________________________________||
def f():
    r = 0
    return r

def subject():
    f()
    f()
    return

def test_sys_settrace(MockCustomizedPdb, mock_state):
    """test with actual sys.settrace()
    """

    thread_asynctask_id = compose_thread_asynctask_id()
    breaks = {
        __name__: ['subject', 'f']
    }
    proxy = PdbProxy(
        thread_asynctask_id=thread_asynctask_id,
        breaks=breaks,
        state=mock_state,
        ci_registry=Mock(),
        statement=""
        )

    trace_org = sys.gettrace()
    sys.settrace(proxy.trace_func)
    subject()
    sys.settrace(trace_org)

    assert 1 == mock_state.update_started.call_count
    assert 1 == mock_state.update_finishing.call_count
    assert 13 == MockCustomizedPdb().trace_dispatch.call_count
    # print(MockCustomizedPdb().trace_dispatch.call_args_list)

##__________________________________________________________________||
