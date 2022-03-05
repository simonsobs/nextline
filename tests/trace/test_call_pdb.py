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

    assert probe == summarize_trace_calls(mock_pdbi.calling_trace)  # type: ignore
    assert mock_pdbi.exited_trace.call_count == mock_pdbi.calling_trace.call_count  # type: ignore


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
def target_trace_func(mock_pdbi_factory):
    y = TraceCallPdb(pdbi_factory=mock_pdbi_factory)
    yield y


@pytest.fixture()
def mock_pdbi_factory(mock_pdbi):
    return lambda: mock_pdbi


@pytest.fixture()
def mock_pdbi(probe_trace_func):
    y = Mock(spec=PdbInterface)
    y.trace = probe_trace_func
    yield y


@pytest.fixture()
def thread():
    yield False
