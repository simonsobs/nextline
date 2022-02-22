import pytest
from unittest.mock import Mock

from typing import Union

from nextline.trace import TraceCallPdb
from nextline.pdb.proxy import PdbInterface

from .funcs import TraceSummary, summarize_trace_calls

from . import module_a


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
    mock_pdbi: Union[Mock, PdbInterface],
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call == target.call
    assert not target.return_.module

    assert ref == probe

    assert 1 == mock_pdbi.open.call_count

    assert probe == summarize_trace_calls(mock_pdbi.calling_trace)
    assert (
        mock_pdbi.exited_trace.call_count == mock_pdbi.calling_trace.call_count
    )


def f():
    module_a.func_a()


@pytest.fixture()
def func():
    yield f


@pytest.fixture(params=[set(), {module_a.__name__}])
def modules_to_skip(request):
    y = request.param
    yield y


@pytest.fixture()
def target_trace_func(mock_pdbi: Union[Mock, PdbInterface]):
    y = TraceCallPdb(pdbi=mock_pdbi)
    yield y


@pytest.fixture()
def mock_pdbi(probe_trace_func):
    y = Mock(spec=PdbInterface)
    y.open.return_value = probe_trace_func
    yield y


@pytest.fixture()
def thread():
    yield False
