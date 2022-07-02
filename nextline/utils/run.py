from __future__ import annotations

from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import Process

import os
import signal
import asyncio

from functools import partial
from typing import Callable, Generic, Optional, TypeVar
from typing_extensions import ParamSpec


_T = TypeVar("_T")
_P = ParamSpec("_P")


async def run_in_process(
    executor_factory: Optional[Callable[[], Executor]],
    func: Callable[_P, _T],
    *func_args: _P.args,
    **func_kwargs: _P.kwargs,
) -> RunInProcess[_T, _P]:
    if executor_factory is None:
        executor_factory = partial(ProcessPoolExecutor, max_workers=1)
    return await RunInProcess.create(
        executor_factory, func, *func_args, **func_kwargs
    )


class RunInProcess(Generic[_T, _P]):
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
        self._process: Optional[Process] = None
        self._future: Optional[asyncio.Future] = None
        self._exc: Optional[BaseException] = None

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._process!r} {self._future}>"

    async def _run(self) -> Optional[_T]:

        with self._executor_factory() as executor:
            loop = asyncio.get_running_loop()
            self._future = loop.run_in_executor(executor, self._func_call)
            if isinstance(executor, ProcessPoolExecutor):
                self._process = list(executor._processes.values())[0]
            self._event.set()
            try:
                return await self._future
            except BrokenProcessPool:
                # NOTE: Not possible to use "as" for unknown reason.
                return None
            except BaseException as e:
                self._exc = e
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
        # NOTE: this method can be as simple as the following one line if it
        # only awaits for the task:
        #
        # return self._task.__await__()
        #
        # "yield from" is used to execute extra code.
        # https://stackoverflow.com/a/48261042/7309855

        ret = yield from self._task.__await__()
        if self._exc:
            raise self._exc
        return ret
