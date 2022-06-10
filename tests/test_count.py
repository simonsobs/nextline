from nextline.types import RunNo, TraceNo, ThreadNo, TaskNo, PromptNo
from nextline.count import (
    RunNoCounter,
    TraceNoCounter,
    ThreadNoCounter,
    TaskNoCounter,
    PromptNoCounter,
)


def test_run_no_counter():
    start = 3
    counter = RunNoCounter(start)
    assert RunNo(start) == counter()
    assert RunNo(start + 1) == counter()
    assert RunNo(start + 2) == counter()


def test_trace_no_counter():
    start = 3
    counter = TraceNoCounter(start)
    assert TraceNo(start) == counter()
    assert TraceNo(start + 1) == counter()
    assert TraceNo(start + 2) == counter()


def test_thread_no_counter():
    start = 3
    counter = ThreadNoCounter(start)
    assert ThreadNo(start) == counter()
    assert ThreadNo(start + 1) == counter()
    assert ThreadNo(start + 2) == counter()


def test_task_no_counter():
    start = 3
    counter = TaskNoCounter(start)
    assert TaskNo(start) == counter()
    assert TaskNo(start + 1) == counter()
    assert TaskNo(start + 2) == counter()


def test_prompt_no_counter():
    start = 3
    counter = PromptNoCounter(start)
    assert PromptNo(start) == counter()
    assert PromptNo(start + 1) == counter()
    assert PromptNo(start + 2) == counter()
