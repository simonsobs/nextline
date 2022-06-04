from __future__ import annotations

import asyncio
import queue
import sys
from typing import Any
from weakref import WeakKeyDictionary

import pytest
from unittest.mock import Mock

from nextline.run import run, Context
from nextline.registrar import Registrar
from nextline.utils import SubscribableDict, ThreadTaskIdComposer
from nextline.utils.func import to_thread


def test_q_done_on_exception(q_done, monkey_patch_run):
    del monkey_patch_run
    context = Context()
    q_commands = Mock()
    with pytest.raises(MockError):
        run(context, q_commands, q_done)
    assert (None, None) == q_done.get()


class MockError(Exception):
    pass


@pytest.fixture
def monkey_patch_run(monkeypatch):
    y = Mock(side_effect=MockError)
    monkeypatch.setattr("nextline.run._run", y)
    yield y


@pytest.mark.asyncio
async def test_one(
    expected_exception,
    context: Context,
    q_commands,
    q_done,
    task_send_commands,
):
    del task_send_commands
    await to_thread(run, context, q_commands, q_done)
    result, exception = q_done.get()
    assert result is None
    if expected_exception:
        with pytest.raises(expected_exception):
            raise exception
    else:
        exception is None


@pytest.fixture
async def task_send_commands(registry, q_commands):
    y = asyncio.create_task(respond_prompt(registry, q_commands))
    yield y
    registry["prompt_info"] = None
    await y


async def respond_prompt(registry, q_commands):
    async for prompt_info in registry.subscribe("prompt_info"):
        if prompt_info is None:
            break
        if not prompt_info.open:
            continue
        q_commands.put((prompt_info.trace_no, "next"))


@pytest.fixture
def context(statement, registrar, registry):
    y = Context(
        statement=statement,
        filename="<string>",
        create_capture_stdout=lambda _: sys.stdout,
        trace_id_factory=ThreadTaskIdComposer(),
        registry=registry,
        registrar=registrar,
    )
    return y


@pytest.fixture
def registrar(registry: SubscribableDict):
    y = Registrar(registry=registry, run_no_start_from=1)
    return y


@pytest.fixture
def registry():
    y = SubscribableDict[str, Any]()
    y["run_no"] = 1
    y["run_no_map"] = WeakKeyDictionary()
    y["trace_no_map"] = WeakKeyDictionary()
    yield y


@pytest.fixture
def statement(statement_params):
    return statement_params[0]


@pytest.fixture
def expected_exception(statement_params):
    return statement_params[1]


SOURCE_ONE = """
import time
time.sleep(0.001)
""".strip()

SOURCE_COMPILE_ERROR = """
def
""".strip()

SOURCE_RUNTIME_ERROR = """
a
""".strip()

CODE_OBJECT = compile(SOURCE_ONE, "<string>", "exec")


@pytest.fixture(
    params=[
        (SOURCE_ONE, None),
        (SOURCE_COMPILE_ERROR, SyntaxError),
        (SOURCE_RUNTIME_ERROR, NameError),
        (CODE_OBJECT, None),
    ]
)
def statement_params(request):
    return request.param


@pytest.fixture
def q_commands():
    y = queue.Queue()
    return y


@pytest.fixture
def q_done():
    y = queue.Queue()
    return y
