import queue
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeAlias

import pytest

from nextline.events import OnStartPrompt
from nextline.spawned import PdbCommand, QueueIn, QueueOut, RunArg, main, set_queues
from nextline.types import RunNo

RunArgParams: TypeAlias = tuple[RunArg, Any, str | None]


def test_one(
    run_arg: RunArg,
    expected_exc : str | None,
    expected_ret : Any,
    call_set_queues : None,
    task_send_commands: None,
) -> None:
    del call_set_queues, task_send_commands
    result = main(run_arg)
    assert result.ret == expected_ret
    if expected_exc:
        assert result.fmt_exc
        assert expected_exc in result.fmt_exc
    else:
        assert not result.fmt_exc


@pytest.fixture
def call_set_queues(queue_in: QueueIn, queue_out: QueueOut) -> None:
    set_queues(queue_in, queue_out)


@pytest.fixture
def task_send_commands(queue_in: QueueIn, queue_out: QueueOut) -> Iterator[None]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        fut = executor.submit(respond_prompt, queue_in, queue_out)
        yield
        queue_out.put(None)  # type: ignore
        fut.result()


def respond_prompt(queue_in: QueueIn, queue_out: QueueOut) -> None:
    while (event := queue_out.get()) is not None:
        if not isinstance(event, OnStartPrompt):
            continue
        command = PdbCommand(
            trace_no=event.trace_no, command='next', prompt_no=event.prompt_no
        )
        queue_in.put(command)


@pytest.fixture
def run_arg(run_arg_params: RunArgParams) -> RunArg:
    return run_arg_params[0]


@pytest.fixture
def expected_ret(run_arg_params: RunArgParams) -> Any:
    return run_arg_params[1]


@pytest.fixture
def expected_exc(run_arg_params: RunArgParams) -> str | None:
    return run_arg_params[2]


SRC_ONE = '''
import time
time.sleep(0.001)
'''.strip()

SRC_COMPILE_ERROR = '''
def
'''.strip()

SRC_RUNTIME_ERROR = '''
a
'''.strip()

SRC_DYNAMIC_EXCEPTION = '''
class MyException(Exception):
    pass

raise MyException()
'''


CODE_OBJECT = compile(SRC_ONE, '<string>', 'exec')


def func_one() -> int:
    return 123


def func_err() -> None:
    1 / 0


SCRIPT_DIR = Path(__file__).resolve().parent / 'example'
SCRIPT_PATH = SCRIPT_DIR / 'script.py'
assert SCRIPT_PATH.is_file()

ERR_PATH = SCRIPT_DIR / 'err.py'
assert ERR_PATH.is_file()

params: list[RunArgParams] = [
    (RunArg(run_no=RunNo(1), statement=SRC_ONE, filename='<string>'), None, None),
    (
        RunArg(run_no=RunNo(1), statement=SRC_COMPILE_ERROR, filename='<string>'),
        None,
        'SyntaxError',
    ),
    (
        RunArg(run_no=RunNo(1), statement=SRC_RUNTIME_ERROR, filename='<string>'),
        None,
        'NameError',
    ),
    (
        RunArg(run_no=RunNo(1), statement=SRC_DYNAMIC_EXCEPTION, filename='<string>'),
        None,
        'MyException',
    ),
    (RunArg(run_no=RunNo(1), statement=CODE_OBJECT), None, None),
    (RunArg(run_no=RunNo(1), statement=func_one), 123, None),
    (RunArg(run_no=RunNo(1), statement=func_err), None, 'ZeroDivisionError'),
    (RunArg(run_no=RunNo(1), statement=SCRIPT_PATH), None, None),
    (RunArg(run_no=RunNo(1), statement=ERR_PATH), None, 'NameError'),
]


@pytest.fixture(params=params)
def run_arg_params(request: pytest.FixtureRequest) -> RunArgParams:
    return request.param


@pytest.fixture
def queue_in() -> QueueIn:
    return queue.Queue()


@pytest.fixture
def queue_out() -> QueueOut:
    return queue.Queue()
