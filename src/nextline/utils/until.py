import asyncio
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import Optional


class UntilNotNoneTimeout(Exception):
    pass


async def until_true(
    func: Callable[[], bool] | Callable[[], Awaitable[bool]],
    /,
    *,
    timeout: Optional[float] = None,
    interval: float = 0,
) -> None:
    '''Return when `func` returns `True` or a truthy value.

    Parameters:
    -----------
    func
        A callable that returns either a boolean or an awaitable that returns a
        boolean.
    timeout
        The maximum number of seconds to wait for `func` to return `True`.
        If `None`, wait indefinitely.
    interval
        The number of seconds to wait before checking `func` again.


    Examples
    --------

    The `func` returns `True` when the third time it is called:

    >>> def gen():
    ...     print('Once')
    ...     yield False
    ...     print('Twice')
    ...     yield False
    ...     print('Thrice')
    ...     yield True
    ...     print('Never reached')
    >>> g = gen()
    >>> func = g.__next__

    >>> asyncio.run(until_true(func))
    Once
    Twice
    Thrice

    The `afunc` is an async version of `func`:

    >>> async def agen():
    ...     print('Once')
    ...     yield False
    ...     print('Twice')
    ...     yield False
    ...     print('Thrice')
    ...     yield True
    ...     print('Never reached')
    >>> g = agen()
    >>> afunc = g.__anext__

    >>> asyncio.run(until_true(afunc))
    Once
    Twice
    Thrice

    An exception will be raised if `timeout` has passed before `True` is
    returned:

    >>> async def gen_none():
    ...     while True:
    ...         yield False
    >>> g = gen_none()
    >>> afunc = g.__anext__

    >>> asyncio.run(until_true(afunc, timeout=0.001))  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    UntilNotNoneTimeout: Timed out after 0.001 seconds.

    '''

    async def call_func() -> bool:
        maybe_awaitable = func()
        if isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def _until_true() -> None:
        while not await call_func():
            await asyncio.sleep(interval)
        return

    # NOTE: For Python 3.11+, `asyncio.timeout` can be used.

    try:
        return await asyncio.wait_for(_until_true(), timeout)
    except asyncio.TimeoutError:
        raise UntilNotNoneTimeout(
            f'Timed out after {timeout} seconds. '
            f'The function has not returned a non-None value: {func!r}'
        )
