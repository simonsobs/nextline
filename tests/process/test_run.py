from __future__ import annotations

import asyncio
import queue
import multiprocessing
from typing import Any, Tuple

# from weakref import WeakKeyDictionary

import pytest
from unittest.mock import Mock

from nextline.process.run import run, RunArg
from nextline.types import RunNo
from nextline.utils.func import to_thread


def test_q_done_on_exception(q_done, monkey_patch_run):
    del monkey_patch_run
    context = RunArg()
    q_commands = Mock()
    with pytest.raises(MockError):
        run(context, q_commands, q_done)
    assert (None, None) == q_done.get()


class MockError(Exception):
    pass


@pytest.fixture
def monkey_patch_run(monkeypatch):
    y = Mock(side_effect=MockError)
    monkeypatch.setattr("nextline.process.run._run", y)
    yield y


@pytest.mark.asyncio
async def test_one(
    expected_exception,
    context: RunArg,
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
async def task_send_commands(q_registrar, q_commands):
    y = asyncio.create_task(to_thread(respond_prompt, q_registrar, q_commands))
    yield y
    q_registrar.put(None)
    await y


def respond_prompt(q_registrar, q_commands):
    while (m := q_registrar.get()) is not None:
        key, value, _ = m
        if key != "prompt_info":
            continue
        prompt_info = value
        if prompt_info is None:
            continue
        if not prompt_info.open:
            continue
        q_commands.put((prompt_info.trace_no, "next"))


@pytest.fixture
def context(
    statement: str,
    q_registrar: multiprocessing.Queue[Tuple[str, Any, bool]],
) -> RunArg:
    y = RunArg(
        run_no=RunNo(1),
        statement=statement,
        filename="<string>",
        queue=q_registrar,
    )
    return y


@pytest.fixture
def q_registrar():
    return multiprocessing.Queue()


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
