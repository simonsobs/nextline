import sys
from itertools import count

from typing import Callable, Union

import pytest
from unittest.mock import Mock

from nextline.utils import Registry
from nextline.pdb.proxy import PdbProxy, Registrar
from nextline.pdb.custom import CustomizedPdb
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
def mock_registrar():
    y = Mock(spec=Registrar)
    yield y


@pytest.fixture()
def proxy(mock_registrar: Registrar):
    modules_to_trace = {"tests.pdb.subject", __name__}

    y = PdbProxy(
        registrar=mock_registrar,
        modules_to_trace=modules_to_trace,
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
    mock_registrar: Union[Mock, Registrar],
    subject: Callable,
):

    trace_org = sys.gettrace()
    sys.settrace(proxy)
    subject()
    sys.settrace(trace_org)

    proxy.close()

    # assert mock_registrar.register.called
    # # print(mock_registrar.register.call_args_list)
    # # TODO: Test contents

    assert 1 == mock_registrar.open.call_count
    assert 1 == mock_registrar.close.call_count
    # assert mock_registrar.entering_cmdloop.called
    # assert mock_registrar.exited_cmdloop.called
    # print(mock_registrar.method_calls)

##__________________________________________________________________||
