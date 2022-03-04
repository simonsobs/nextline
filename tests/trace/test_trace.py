import pytest
from unittest.mock import Mock

from typing import Set

from nextline.trace import Trace
from nextline.pdb.proxy import PdbInterfaceFactory, PdbInterface
from nextline.utils import SubscribableDict
from nextline.registry import PdbCIRegistry

from .funcs import TraceSummary

from . import module_a


def test_one(
    target: TraceSummary,
    probe: TraceSummary,
    ref: TraceSummary,
):
    assert ref.call.module
    assert ref.return_.module
    assert ref.call == target.call
    assert not target.return_.module

    assert ref == probe


def f():
    module_a.func_a()


@pytest.fixture()
def func():
    yield f


@pytest.fixture()
def thread():
    yield False


@pytest.fixture()
def target_trace_func(modules_to_trace: Set[str]):
    y = Trace(
        registry=Mock(spec=SubscribableDict),
        pdb_ci_registry=Mock(spec=PdbCIRegistry),
        modules_to_trace=modules_to_trace,
    )
    yield y


@pytest.fixture()
def modules_to_trace():
    y = set()
    yield y


@pytest.fixture()
def mock_pdbi(probe_trace_func):
    y = Mock(spec=PdbInterface)
    y.open.return_value = probe_trace_func
    yield y


@pytest.fixture(autouse=True)
def MockPdbInterfaceFactory(mock_pdbi, monkeypatch):
    mock_create_pdbi = Mock(return_value=mock_pdbi)
    y = Mock(spec=PdbInterfaceFactory, return_value=mock_create_pdbi)
    monkeypatch.setattr("nextline.trace.PdbInterfaceFactory", y)
    yield y
