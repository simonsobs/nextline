from __future__ import annotations

import time
import signal
from functools import partial
from concurrent.futures import Executor, ProcessPoolExecutor
from multiprocessing import Event
from types import FrameType
from typing import TYPE_CHECKING, Callable, NoReturn, Optional

import pytest

from nextline.utils import run_in_process

if TYPE_CHECKING:
    from multiprocessing import _EventType


_event: Optional[_EventType] = None


def initializer(event: _EventType) -> None:
    global _event
    _event = event


class MockError(Exception):
    pass


class Handled(Exception):
    pass


def func() -> str:
    return "foo"


def func_raise() -> NoReturn:
    raise MockError()


def func_slow() -> NoReturn:
    assert _event
    _event.set()
    time.sleep(10)
    raise RuntimeError("to be terminated by here")


def func_slow_catch() -> str:
    assert _event
    try:
        _event.set()
        time.sleep(10)
    except KeyboardInterrupt:
        return "foo"
    return "bar"


def handler(signum: signal._SIGNUM, frame: FrameType):
    raise Handled


def func_slow_handle() -> str:
    assert _event
    signal.signal(signal.SIGTERM, handler)  # type: ignore
    try:
        _event.set()
        time.sleep(10)
    except Handled:
        return "foo"
    return "bar"


async def test_one(executor_factory: Callable[[], Executor]) -> None:
    r = await run_in_process(executor_factory, func)
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_default_executor() -> None:
    r = await run_in_process(None, func)
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_repr(executor_factory: Callable[[], Executor]) -> None:
    r = await run_in_process(executor_factory, func)
    repr(r)
    await r


async def test_error(executor_factory: Callable[[], Executor]) -> None:
    r = await run_in_process(executor_factory, func_raise)
    with pytest.raises(MockError):
        await r
    assert r._process
    assert r._process.exitcode == 0


async def test_interrupt(
    executor_factory: Callable[[], Executor], event: _EventType
) -> None:
    r = await run_in_process(executor_factory, func_slow)
    event.wait()
    r.interrupt()
    with pytest.raises(KeyboardInterrupt):
        await r
    assert r._process
    assert r._process.exitcode == 0


async def test_interrupt_catch(
    executor_factory: Callable[[], Executor], event: _EventType
) -> None:
    r = await run_in_process(executor_factory, func_slow_catch)
    event.wait()
    r.interrupt()
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_terminate(
    executor_factory: Callable[[], Executor], event: _EventType
) -> None:
    r = await run_in_process(executor_factory, func_slow)
    event.wait()
    r.terminate()
    assert None is await r
    assert r._process
    assert r._process.exitcode == -signal.SIGTERM


async def test_terminate_handle(
    executor_factory: Callable[[], Executor], event: _EventType
) -> None:
    r = await run_in_process(executor_factory, func_slow_handle)
    event.wait()
    r.terminate()
    assert "foo" == await r
    assert r._process
    assert r._process.exitcode == 0


async def test_kill(
    executor_factory: Callable[[], Executor], event: _EventType
) -> None:
    r = await run_in_process(executor_factory, func_slow)
    event.wait()
    r.kill()
    assert None is await r
    assert r._process
    assert r._process.exitcode == -signal.SIGKILL


@pytest.fixture
def executor_factory(event: _EventType) -> Callable[[], Executor]:
    return partial(
        ProcessPoolExecutor,
        max_workers=1,
        initializer=initializer,
        initargs=(event,),
    )


@pytest.fixture
def event() -> _EventType:
    return Event()
