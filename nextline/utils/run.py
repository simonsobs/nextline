from __future__ import annotations

import asyncio
import os
import signal
from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from functools import partial
from logging import getLogger
from multiprocessing import Process
from typing import Callable, Generic, Optional, TypeVar

from typing_extensions import TypeAlias

_T = TypeVar("_T")


ExecutorFactory: TypeAlias = 'Callable[[], Executor]'


async def run_in_process(
    func: Callable[[], _T], executor_factory: Optional[ExecutorFactory] = None
) -> RunInProcess[_T]:
    '''Call a function in a separate process and return an awaitable.

    Use functools.partial to pass arguments to the function.

    Example:

    >>> async def simple_example():
    ...
    ...     # Run pow(2, 3), which returns 8, in a separate process.
    ...     starting = run_in_process(partial(pow, 2, 3))
    ...
    ...     # Wait for the process to start.
    ...     running = await starting
    ...
    ...     # Wait for the process to finish.
    ...     result = await running
    ...
    ...     return result

    >>> asyncio.run(simple_example())
    8

    '''

    if executor_factory is None:
        executor_factory = partial(ProcessPoolExecutor, max_workers=1)
    return await RunInProcess.create(executor_factory, func)


class RunInProcess(Generic[_T]):
    @classmethod
    async def create(cls, executor_factory: ExecutorFactory, func: Callable[[], _T]):
        self = cls(executor_factory, func)
        assert await self._event.wait()
        return self

    def __init__(self, executor_factory: ExecutorFactory, func: Callable[[], _T]):
        self._executor_factory = executor_factory
        self._func_call = func
        self._event = asyncio.Event()
        self._task = asyncio.create_task(self._run())
        self._process: Optional[Process] = None
        self._future: Optional[asyncio.Future] = None
        self._exc: Optional[BaseException] = None
        self._logger = getLogger(__name__)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._process!r} {self._future}>"

    async def _run(self) -> Optional[_T]:
        '''Called in __init__(), awaited in __await__().'''

        try:
            with self._executor_factory() as executor:
                loop = asyncio.get_running_loop()
                self._future = loop.run_in_executor(executor, self._func_call)
                if isinstance(executor, ProcessPoolExecutor):
                    self._process = list(executor._processes.values())[0]
                    self._logger.info(f'A process ({self._process.pid}) created.')
                    # TODO: Get the process created time here.
                self._event.set()
                try:
                    return await self._future
                except BrokenProcessPool:
                    # NOTE: Not possible to use "as" for unknown reason.
                    return None
                except BaseException as e:
                    self._exc = e
                    return None
        finally:
            if self._process:
                pid = self._process.pid
                exitcode = self._process.exitcode
                exit_fmt = f'{exitcode}'
                if exitcode:
                    if name := _exitcode_to_name.get(exitcode):
                        exit_fmt = f'{exitcode} ({name})'
                self._logger.info(f'The process ({pid}) exited: {exit_fmt}.')
                # TODO: Get the process exited time here.

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


# Originally copied from
# https://github.com/python/cpython/blob/3.8/Lib/multiprocessing/process.py#L425-L429
_exitcode_to_name = {
    -signum: f'-{name}'
    for name, signum in signal.__dict__.items()
    if name[:3] == 'SIG' and '_' not in name
}
