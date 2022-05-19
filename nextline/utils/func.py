from __future__ import annotations

import threading
import asyncio
import functools

from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    AsyncIterator,
    Iterable,
    Set,
    Tuple,
    TypeVar,
)

if TYPE_CHECKING:
    from threading import Thread
    from asyncio import Task, Future


def current_task_or_thread() -> Task | Thread:
    """The asyncio task object if in a task, else the thread object"""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return task or threading.current_thread()


try:
    from asyncio import to_thread  # type: ignore
except ImportError:
    # for Python 3.8
    # to_thread() is new in Python 3.9

    async def to_thread(func, /, *args, **kwargs):  # type: ignore
        loop = asyncio.get_running_loop()
        func_call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)


T = TypeVar("T")


async def agen_with_wait(
    agen: AsyncIterator[T],
) -> AsyncGenerator[
    T | Tuple[Tuple[Future, ...], Tuple[Future, ...]], Iterable[Future]
]:
    """Yield from the agen while waiting for received tasks

    Used to raise an exception from tasks
    """
    done: Set[Future] = set()
    pending: Set[Future] = set()
    anext = asyncio.ensure_future(agen.__anext__())
    while True:
        done_, pending_ = await asyncio.wait(
            pending | {anext},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in done_ - {anext}:
            if exc := t.exception():
                anext.cancel()
                raise exc
        if anext in done_:
            try:
                item = anext.result()
            except StopAsyncIteration:
                break
            done_.remove(anext)
            done |= done_
        else:
            done |= done_
            continue
        pending &= pending_
        new = yield item
        if new is not None:
            pending |= set(new)
            yield tuple(done), tuple(pending)
            done.clear()
        anext = asyncio.ensure_future(agen.__anext__())


async def merge_aiters(
    *aiters: AsyncIterator[T],
) -> AsyncIterator[Tuple[int, T]]:
    aiter_map = {a: i for i, a in enumerate(aiters)}
    task_map = {
        asyncio.ensure_future(a.__anext__()): a for a in aiter_map.keys()
    }
    tasks = set(task_map.keys())
    while tasks:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        tasks = pending
        while done:
            task = done.pop()
            try:
                item = task.result()
            except StopAsyncIteration:
                continue
            aiter = task_map[task]
            yield aiter_map[aiter], item
            task = asyncio.ensure_future(aiter.__anext__())
            tasks.add(task)
            task_map[task] = aiter
