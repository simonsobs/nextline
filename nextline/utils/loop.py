from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def ToLoop() -> Callable[[Callable[[Any], T]], T]:
    """Create a function that calls a function in the same asyncio event loop

    A running asyncio event loop needs to exist in the thread in which this
    function is called. The returned function can be called in any thread. A
    function given to the returned function will be called in the event loop in
    the thread in which this function is called.
    """
    loop = asyncio.get_running_loop()

    def in_the_same_running_loop():
        try:
            loop_ = asyncio.get_running_loop()
        except RuntimeError:
            return False
        return loop is loop_

    def to_loop(func: Callable[[Any], T], /, *args, **kwargs) -> T:
        func_ = partial(func, *args, **kwargs)

        if in_the_same_running_loop():
            return func_()

        if loop.is_closed():
            raise RuntimeError(f"The loop is closed: {loop}")

        # In another thread

        async def afunc():
            return func_()

        fut = asyncio.run_coroutine_threadsafe(afunc(), loop)
        return fut.result()

    return to_loop
