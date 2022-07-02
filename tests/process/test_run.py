from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import queue

import pytest

from nextline.process.run import run, RunArg, set_queues
from nextline.types import RunNo


def test_one(
    expected_exception,
    run_arg: RunArg,
    call_set_queues,
    task_send_commands,
):
    del call_set_queues, task_send_commands
    result, exception = run(run_arg)
    assert result is None
    if expected_exception:
        assert exception
        with pytest.raises(expected_exception):
            raise exception
    else:
        exception is None


@pytest.fixture
def call_set_queues(q_registrar, q_commands):
    set_queues(q_commands, q_registrar)
    yield


@pytest.fixture
def task_send_commands(q_registrar, q_commands):
    with ThreadPoolExecutor(max_workers=1) as executor:
        fut = executor.submit(respond_prompt, q_registrar, q_commands)
        yield
        q_registrar.put(None)
        fut.result()


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
        q_commands.put(("next", prompt_info.prompt_no, prompt_info.trace_no))


@pytest.fixture
def run_arg(statement: str) -> RunArg:
    y = RunArg(run_no=RunNo(1), statement=statement, filename="<string>")
    return y


@pytest.fixture
def q_registrar():
    return queue.Queue()


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
