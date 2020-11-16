import sys
import asyncio

import pytest
from unittest.mock import Mock, MagicMock

from nextline.trace import State, compose_thread_asynctask_id
from nextline.pdb.proxy import PdbProxy
from nextline.pdb.custom import CustomizedPdb

from . import subject

##__________________________________________________________________||
@pytest.fixture()
def mock_state():
    y = Mock(spec=State)
    yield y

##__________________________________________________________________||
params = [
    pytest.param(subject.f, id="simple"),
    pytest.param(subject.subject, id="nested-func"),
    pytest.param(subject.run_a, id="asyncio")
]

@pytest.mark.parametrize('subject', params)
def test_sys_settrace(mock_state, snapshot, subject):
    """test with actual sys.settrace()
    """

    thread_asynctask_id = compose_thread_asynctask_id()

    # unused
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

    proxy.pdb.trace_dispatch = Mock()

    trace_org = sys.gettrace()
    sys.settrace(proxy.trace_func)
    subject()
    sys.settrace(trace_org)

    assert 1 == mock_state.update_started.call_count
    assert 1 == mock_state.update_finishing.call_count

    assert 1 == mock_trace.returning.call_count

    # unpack trace call results
    trace_results = []
    trace_dispatch = proxy.pdb.trace_dispatch
    while trace_dispatch.call_count:
        trace_results.append([
            (c.args[0].f_code.co_name, c.args[1], asyncio.isfuture(c.args[2]))
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

    # from pprint import pprint
    # pprint(trace_results)
    snapshot.assert_match(trace_results)

##__________________________________________________________________||
