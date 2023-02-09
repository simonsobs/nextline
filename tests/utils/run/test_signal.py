from __future__ import annotations

import signal
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import Event
from types import FrameType
from typing import TYPE_CHECKING, NoReturn, Optional

import pytest

from nextline.utils import ExecutorFactory, run_in_process

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event as _EventType

#

_event: Optional[_EventType] = None


def initializer(event: _EventType) -> None:
    global _event
    _event = event


#


def func_sleep() -> NoReturn:
    assert _event
    _event.set()
    time.sleep(10)
    raise RuntimeError("to be terminated by here")


async def test_interrupt(executor_factory: ExecutorFactory, event: _EventType) -> None:
    r = await run_in_process(func_sleep, executor_factory)
    event.wait()
    r.interrupt()
    with pytest.raises(KeyboardInterrupt):
        await r
    assert r._process
    assert r._process.exitcode == 0


async def test_terminate(executor_factory: ExecutorFactory, event: _EventType) -> None:
    r = await run_in_process(func_sleep, executor_factory)
    event.wait()
    r.terminate()
    assert None is await r
    assert r._process
    assert r._process.exitcode == -signal.SIGTERM


async def test_kill(executor_factory: ExecutorFactory, event: _EventType) -> None:
    r = await run_in_process(func_sleep, executor_factory)
    event.wait()
    r.kill()
    assert None is await r
    assert r._process
    assert r._process.exitcode == -signal.SIGKILL


#


def func_catch_interrupt() -> str:
    assert _event
    try:
        _event.set()
        time.sleep(10)
    except KeyboardInterrupt:
        return "foo"
    return "bar"


async def test_interrupt_catch(
    executor_factory: ExecutorFactory, event: _EventType
) -> None:
    r = await run_in_process(func_catch_interrupt, executor_factory)
    event.wait()
    r.interrupt()
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


#


class Handled(Exception):
    pass


def handler(signum: signal._SIGNUM, frame: FrameType):
    raise Handled


def func_handle_terminate() -> str:
    assert _event
    signal.signal(signal.SIGTERM, handler)  # type: ignore
    try:
        _event.set()
        time.sleep(10)
    except Handled:
        return "foo"
    return "bar"


async def test_terminate_handle(
    executor_factory: ExecutorFactory, event: _EventType
) -> None:
    r = await run_in_process(func_handle_terminate, executor_factory)
    event.wait()
    r.terminate()
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


@pytest.fixture
def executor_factory(event: _EventType) -> ExecutorFactory:
    return partial(
        ProcessPoolExecutor,
        max_workers=1,
        initializer=initializer,
        initargs=(event,),
    )


@pytest.fixture
def event() -> _EventType:
    return Event()
