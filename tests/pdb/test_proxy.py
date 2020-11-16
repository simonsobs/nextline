import sys

import pytest
from unittest.mock import Mock, MagicMock

from nextline.trace import State, compose_thread_asynctask_id
from nextline.pdb.proxy import PdbProxy
from nextline.pdb.custom import CustomizedPdb

##__________________________________________________________________||
@pytest.fixture()
def MockCustomizedPdb(monkeypatch):
    mock_instance = Mock(spec=CustomizedPdb)
    mock_instance.is_skipped_module.return_value = False
    # mock_instance.trace_dispatch.return_value = None
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

def test_sys_settrace(MockCustomizedPdb, mock_state, snapshot):
    """test with actual sys.settrace()
    """

    thread_asynctask_id = compose_thread_asynctask_id()
    breaks = {
        __name__: ['subject', 'f']
    }
    mock_trace = Mock()

    proxy = PdbProxy(
        thread_asynctask_id=thread_asynctask_id,
        trace=mock_trace,
        breaks=breaks,
        state=mock_state,
        ci_registry=Mock(),
        statement=""
        )

    trace_org = sys.gettrace()
    sys.settrace(proxy.trace_func)
    subject()
    sys.settrace(trace_org)

    assert 1 == MockCustomizedPdb.call_count

    assert 1 == mock_state.update_started.call_count
    assert 1 == mock_state.update_finishing.call_count

    assert 1 == mock_trace.returning.call_count

    # unpack trace call results
    trace_results = []
    trace_dispatch = MockCustomizedPdb.return_value.trace_dispatch
    while trace_dispatch.call_count:
        trace_results.append([
            (c.args[0].f_code.co_name, *c.args[1:])
            for c in trace_dispatch.call_args_list
        ])
        trace_dispatch = trace_dispatch.return_value

    # e.g.,
    # [
    #     [('subject', 'call', None), ('f', 'call', None), ('f', 'call', None)],
    #     [('subject', 'line', None), ('f', 'line', None), ('f', 'line', None)],
    #     [('f', 'line', None), ('subject', 'line', None), ('f', 'line', None)],
    #     [('f', 'return', 0), ('f', 'return', 0), ('subject', 'line', None)],
    #     [('subject', 'return', None)]
    # ]

    snapshot.assert_match(trace_results)

##__________________________________________________________________||
