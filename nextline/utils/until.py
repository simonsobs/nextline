import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional, TypeVar

T = TypeVar('T')


class UntilNotNoneTimeout(Exception):
    pass


async def until_not_none(
    func: Callable[[], Awaitable[T | None]],
    /,
    *,
    timeout: Optional[float] = None,
    interval: float = 0,
) -> T:
    '''Return the first non-None value from `func`.


    Examples
    --------

    Define a function `func` that returns a non-None value after having
    returned `None` twice:

    >>> async def gen():
    ...     yield None
    ...     yield None
    ...     yield 42
    >>> g = gen()
    >>> func = g.__anext__

    The first non-None value 42 will be returned:

    >>> asyncio.run(until_not_none(g.__anext__))
    42


    An exception will be raised if `timeout` has passed before a non-None value
    is returned:

    >>> async def gen_none():
    ...     while True:
    ...         yield None
    >>> g = gen_none()
    >>> func = g.__anext__

    >>> asyncio.run(until_not_none(func, timeout=0.001))  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    UntilNotNoneTimeout: Timed out after 0.001 seconds.



    '''

    async def _until_not_none() -> T:
        while (ret := await func()) is None:
            await asyncio.sleep(interval)
        return ret

    # NOTE: For Python 3.11+, `asyncio.timeout` can be used.

    try:
        return await asyncio.wait_for(_until_not_none(), timeout)
    except asyncio.TimeoutError:
        raise UntilNotNoneTimeout(
            f'Timed out after {timeout} seconds. '
            f'The function has not returned a non-None value: {func!r}'
        )
