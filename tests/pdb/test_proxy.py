import sys
import asyncio

import pytest
from unittest.mock import Mock

from nextline.trace import Trace, State, compose_thread_asynctask_id
from nextline.pdb.proxy import PdbProxy
from nextline.pdb.custom import CustomizedPdb

from . import subject

##__________________________________________________________________||
@pytest.fixture()
def mock_trace():
    y = Mock(spec=Trace)
    yield y

@pytest.fixture()
def mock_state():
    y = Mock(spec=State)
    yield y

@pytest.fixture()
def proxy(mock_trace, mock_state):
    thread_asynctask_id = compose_thread_asynctask_id()

    # unused
    breaks = {
        __name__: ['subject', 'f']
    }

    y = PdbProxy(
        thread_asynctask_id=thread_asynctask_id,
        trace=mock_trace,
        breaks=breaks,
        state=mock_state,
        ci_registry=Mock()
        )

    y.pdb.trace_dispatch = Mock()

    yield y

##__________________________________________________________________||
def unpack_trace_dispatch_call(trace_dispatch):
    trace_results = []
    while trace_dispatch.call_count:
        trace_results.append([
            (c.args[0].f_code.co_name, c.args[1], asyncio.isfuture(c.args[2]))
            for c in trace_dispatch.call_args_list
        ])
        trace_dispatch = trace_dispatch.return_value

    # e.g.,
    # trace_results = [
    #     [('run_a', 'call', False), ('<lambda>', 'call', False), ('a', 'call', False), ('a', 'call', False)],
    #     [('run_a', 'line', False), ('<lambda>', 'line', False), ('a', 'line', False), ('a', 'exception', False)],
    #     [('<lambda>', 'return', False), ('a', 'return', True), ('a', 'line', False), ('run_a', 'return', False)],
    #     [('a', 'return', False)]
    # ]

    return trace_results

##__________________________________________________________________||
params = [
    pytest.param(subject.f, id="simple"),
    pytest.param(subject.subject, id="nested-func"),
    pytest.param(subject.call_gen, id="yield"),
    pytest.param(subject.run_a, id="asyncio")
]

@pytest.mark.skipif(sys.version_info < (3, 9), reason="co_name <lambda> is different ")
@pytest.mark.parametrize('subject', params)
def test_proxy(proxy, mock_trace, mock_state, snapshot, subject):
    """test PdbProxy

    """
    # TODO: the test needs to be restructured so that, for example, a
    # coroutine or a generator can be the outermost scope.

    trace_org = sys.gettrace()
    sys.settrace(proxy.trace_func)
    subject()
    sys.settrace(trace_org)

    assert 1 == mock_state.update_started.call_count
    assert 1 == mock_state.update_finishing.call_count

    assert 1 == mock_trace.returning.call_count

    trace_results = unpack_trace_dispatch_call(proxy.pdb.trace_dispatch)
    snapshot.assert_match(trace_results)

##__________________________________________________________________||
