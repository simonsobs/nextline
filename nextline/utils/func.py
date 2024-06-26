import asyncio
import threading
import warnings
from asyncio import Future, Task
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterable
from threading import Thread
from typing import TypeVar


def current_task_or_thread() -> Task | Thread:
    '''The asyncio task object if in a task, else the thread object'''
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return task or threading.current_thread()


T = TypeVar('T')


async def to_aiter(
    iterable: Iterable[T], /, *, thread: bool = True
) -> AsyncIterator[T]:
    '''Wrap iterable so can be used with `async for`

    The iteration can be blocking as it is run in a separate thread by default.

    Parameters
    ----------
    iterable
        The iterable to wrap
    thread
        Whether to run the iterable in a separate thread

    Examples
    --------
    >>> async def main():
    ...     async for i in to_aiter(range(3)):
    ...         print(i)
    >>> asyncio.run(main())
    0
    1
    2
    '''
    iterator = iter(iterable)

    class _EndOfIteration(Exception):
        pass

    def _replace_stop_iteration(f: Callable[[], T]) -> T:
        '''Raise a custom exception when `StopIteration` is raised.

        This is because coroutines cannot raise `StopIteration` and `to_thread`
        does not propagate `StopIteration`.
        '''
        try:
            return f()
        except StopIteration:
            raise _EndOfIteration

    async def _call_next_in_thread() -> T:
        return await asyncio.to_thread(_replace_stop_iteration, lambda: next(iterator))

    async def _call_next() -> T:
        return _replace_stop_iteration(lambda: next(iterator))

    _next = _call_next_in_thread if thread else _call_next

    while True:
        try:
            item = await _next()
        except _EndOfIteration:
            break
        yield item
        await asyncio.sleep(0)  # Let other tasks run


def aiterable(iterable: Iterable[T]) -> AsyncIterator[T]:
    '''Wrap iterable so can be used with `async for`'''
    warnings.warn(
        'aiterable is deprecated, use to_aiter',
        DeprecationWarning,
        stacklevel=2,
    )
    return to_aiter(iterable, thread=False)


async def agen_with_wait(
    agen: AsyncIterator[T],
) -> AsyncGenerator[
    T | tuple[tuple[Future, ...], tuple[Future, ...]], Iterable[Future]
]:
    '''Yield from the agen while waiting for received tasks

    Used to raise an exception from tasks
    '''
    done = set[Future]()
    pending = set[Future]()
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
) -> AsyncIterator[tuple[int, T]]:
    aiter_map = {a: i for i, a in enumerate(aiters)}
    task_map = {asyncio.ensure_future(a.__anext__()): a for a in aiter_map.keys()}
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
