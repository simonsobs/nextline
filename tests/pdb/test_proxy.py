import sys
from itertools import count

from typing import Callable, Union

import pytest
from unittest.mock import Mock

from nextline.utils import Registry
from nextline.pdb.proxy import PdbProxy, CustomizedPdb
from nextline.trace import UniqThreadTaskIdComposer


class MockCustomizedPdb(CustomizedPdb):
    """Skip the command loop"""
    def trace_dispatch(self, frame, event, arg):
        return super().trace_dispatch(frame, event, arg)

    def _cmdloop(self):
        self._proxy.entering_cmdloop()
        # super()._cmdloop()
        self._proxy.exited_cmdloop()


@pytest.fixture(autouse=True)
def monkeypatch_customized_pdb(monkeypatch):
    monkeypatch.setattr("nextline.pdb.proxy.CustomizedPdb", MockCustomizedPdb)


@pytest.fixture()
def mock_registry():
    y = Mock(spec=Registry)
    yield y


@pytest.fixture()
def proxy(mock_registry: Registry):
    thread_asynctask_id = UniqThreadTaskIdComposer()()

    modules_to_trace = {"tests.pdb.subject", __name__}

    prompting_counter = count(1).__next__

    y = PdbProxy(
        thread_asynctask_id=thread_asynctask_id,
        modules_to_trace=modules_to_trace,
        registry=mock_registry,
        ci_registry=Mock(),
        prompting_counter=prompting_counter,
    )

    yield y


def func_c():
    return


def func_b():
    func_c()


def func_a():
    func_b()
    return


params = [
    pytest.param(func_a, id="simple"),
]


@pytest.mark.parametrize("subject", params)
def test_proxy(
    proxy: PdbProxy,
    mock_registry: Union[Mock, Registry],
    subject: Callable,
):

    trace_org = sys.gettrace()
    sys.settrace(proxy)
    subject()
    sys.settrace(trace_org)

    proxy.close()

    assert mock_registry.register.called
    # print(mock_registry.register.call_args_list)
    # TODO: Test contents

    assert 1 == mock_registry.open_register.call_count
    assert 1 == mock_registry.register_list_item.call_count
    assert 1 == mock_registry.close_register.call_count


##__________________________________________________________________||
