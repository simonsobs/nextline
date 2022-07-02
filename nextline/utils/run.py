from __future__ import annotations

from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

import os
import signal
import asyncio

from functools import partial
from typing import Callable, Generic, Optional, TypeVar
from typing_extensions import ParamSpec


_T = TypeVar("_T")
_P = ParamSpec("_P")


async def run_in_executor(
    executor_factory: Callable[[], Executor],
    func: Callable[_P, _T],
    *func_args: _P.args,
    **func_kwargs: _P.kwargs,
) -> Run[_T, _P]:
    return await Run.create(executor_factory, func, *func_args, **func_kwargs)


class Run(Generic[_T, _P]):
    @classmethod
    async def create(
        cls,
        executor_factory: Callable[[], Executor],
        func: Callable[_P, _T],
        *func_args: _P.args,
        **func_kwargs: _P.kwargs,
    ):
        self = cls(executor_factory, func, *func_args, **func_kwargs)
        assert await self._event.wait()
        return self

    def __init__(
        self,
        executor_factory: Callable[[], Executor],
        func: Callable[_P, _T],
        *func_args: _P.args,
        **func_kwargs: _P.kwargs,
    ):
        self._executor_factory = executor_factory
        self._func_call = partial(func, *func_args, **func_kwargs)
        self._event = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> Optional[_T]:

        with self._executor_factory() as executor:
            loop = asyncio.get_running_loop()
            f = loop.run_in_executor(executor, self._func_call)
            if isinstance(executor, ProcessPoolExecutor):
                self._process = list(executor._processes.values())[0]
            self._event.set()
            try:
                return await f
            except BrokenProcessPool:
                print("BrokenProcessPool")
                return None

    def interrupt(self) -> None:
        if self._process and self._process.pid:
            os.kill(self._process.pid, signal.SIGINT)

    def terminate(self) -> None:
        if self._process:
            self._process.terminate()

    def kill(self) -> None:
        if self._process:
            self._process.kill()

    def __await__(self):
        return self._task.__await__()
