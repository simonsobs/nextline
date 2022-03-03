from __future__ import annotations

import threading
import asyncio
import functools

from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    Iterable,
    Union,
    Set,
    Any,
)

if TYPE_CHECKING:
    from threading import Thread
    from asyncio import Task


def current_task_or_thread() -> Union[Task, Thread]:
    """The asyncio task object if in a task, else the thread object"""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return task or threading.current_thread()


try:
    from asyncio import to_thread
except ImportError:
    # for Python 3.8
    # to_thread() is new in Python 3.9

    async def to_thread(func, /, *args, **kwargs):  # type: ignore
        loop = asyncio.get_running_loop()
        func_call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)


async def agen_with_wait(
    agen: AsyncGenerator,
) -> AsyncGenerator[Any, Iterable[Task]]:
    """Yield from the agen while waiting for received tasks

    Used to raise an exception from tasks
    """
    done: Set[Task] = set()
    pending: Set[Task] = set()
    anext = asyncio.create_task(agen.__anext__())
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
        anext = asyncio.create_task(agen.__anext__())
