from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

import pytest

from nextline.spawned import (
    OnStartPrompt,
    PdbCommand,
    QueueIn,
    QueueOut,
    RunArg,
    main,
    set_queues,
)
from nextline.types import RunNo


def test_one(
    expected_exception,
    run_arg: RunArg,
    call_set_queues,
    task_send_commands,
):
    del call_set_queues, task_send_commands
    result = main(run_arg)
    assert result.ret is None
    if expected_exception:
        assert result.exc
        with pytest.raises(expected_exception):
            raise result.exc
    else:
        assert result.exc is None


@pytest.fixture
def call_set_queues(queue_in: QueueIn, queue_out: QueueOut):
    set_queues(queue_in, queue_out)
    yield


@pytest.fixture
def task_send_commands(queue_in: QueueIn, queue_out: QueueOut):
    with ThreadPoolExecutor(max_workers=1) as executor:
        fut = executor.submit(respond_prompt, queue_in, queue_out)
        yield
        queue_out.put(None)  # type: ignore
        fut.result()


def respond_prompt(queue_in: QueueIn, queue_out: QueueOut):
    while (event := queue_out.get()) is not None:
        if not isinstance(event, OnStartPrompt):
            continue
        command = PdbCommand(
            trace_no=event.trace_no, command='next', prompt_no=event.prompt_no
        )
        queue_in.put(command)


@pytest.fixture
def run_arg(run_arg_params) -> RunArg:
    return run_arg_params[0]


@pytest.fixture
def expected_exception(run_arg_params):
    return run_arg_params[1]


SOURCE_ONE = '''
import time
time.sleep(0.001)
'''.strip()

SOURCE_COMPILE_ERROR = '''
def
'''.strip()

SOURCE_RUNTIME_ERROR = '''
a
'''.strip()

CODE_OBJECT = compile(SOURCE_ONE, '<string>', 'exec')

params = [
    (RunArg(run_no=RunNo(1), statement=SOURCE_ONE, filename='<string>'), None),
    (
        RunArg(run_no=RunNo(1), statement=SOURCE_COMPILE_ERROR, filename='<string>'),
        SyntaxError,
    ),
    (
        RunArg(run_no=RunNo(1), statement=SOURCE_RUNTIME_ERROR, filename='<string>'),
        NameError,
    ),
    # (RunArg(run_no=RunNo(1), statement=CODE_OBJECT, filename='<string>'), None),
]


@pytest.fixture(params=params)
def run_arg_params(request) -> Tuple[RunArg, type[BaseException] | None]:
    return request.param


@pytest.fixture
def queue_in() -> QueueIn:
    return queue.Queue()


@pytest.fixture
def queue_out() -> QueueOut:
    return queue.Queue()
