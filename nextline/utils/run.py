from __future__ import annotations

import asyncio
import os
import signal
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timezone
from functools import partial
from logging import getLogger
from multiprocessing import Process
from typing import Callable, Generator, Generic, Optional, Tuple, TypeVar

from typing_extensions import TypeAlias

_T = TypeVar("_T")


ExecutorFactory: TypeAlias = 'Callable[[], ProcessPoolExecutor]'


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

    process: Optional[Process] = None
    event = asyncio.Event()

    async def _run(
        executor_factory: ExecutorFactory, func: Callable[[], _T]
    ) -> Tuple[Optional[_T], Optional[BaseException]]:
        nonlocal process

        try:
            with executor_factory() as executor:
                loop = asyncio.get_running_loop()
                future = loop.run_in_executor(executor, func)
                process = list(executor._processes.values())[0]

                now = datetime.now(timezone.utc)
                now_fmt = now.strftime('%Y-%m-%d %H:%M:%S (%Z)')
                msg = f'Process ({process.pid}) created at {now_fmt}.'
                logger = getLogger(__name__)
                logger.info(msg)

                event.set()
                ret = None
                exc = None
                try:
                    ret = await future
                except BrokenProcessPool:
                    # NOTE: Not possible to use "as" for unknown reason.
                    pass
                except BaseException as e:
                    exc = e
                return ret, exc

        finally:
            if process:
                pid = process.pid
                now = datetime.now(timezone.utc)
                now_fmt = now.strftime('%Y-%m-%d %H:%M:%S (%Z)')
                exitcode = process.exitcode
                exit_fmt = f'{exitcode}'
                if exitcode and (name := _exitcode_to_name.get(exitcode)):
                    exit_fmt = f'{exitcode} ({name})'
                msg = f'Process ({pid}) exited at {now_fmt}. Exitcode: {exit_fmt}.'
                logger = getLogger(__name__)
                logger.info(msg)

    task = asyncio.create_task(_run(executor_factory=executor_factory, func=func))
    await event.wait()
    assert process
    ret = RunInProcess[_T](process=process, task=task)
    return ret


class RunInProcess(Generic[_T]):
    def __init__(
        self,
        process: Process,
        task: asyncio.Task[Tuple[Optional[_T], Optional[BaseException]]],
    ):
        self._process = process
        self._task = task

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._process!r} {self._task}>"

    def interrupt(self) -> None:
        if self._process.pid:
            os.kill(self._process.pid, signal.SIGINT)

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()

    def __await__(self) -> Generator[None, None, Optional[_T]]:
        # "yield from" is used to execute extra code.
        # Otherwise, the method would be as simple as:
        #
        #   return self._task.__await__()
        #
        # https://stackoverflow.com/a/48261042/7309855

        ret, exc = yield from self._task.__await__()
        if exc:
            raise exc
        return ret


# Originally copied from
# https://github.com/python/cpython/blob/3.8/Lib/multiprocessing/process.py#L425-L429
_exitcode_to_name = {
    -signum: f'-{name}'
    for name, signum in signal.__dict__.items()
    if name[:3] == 'SIG' and '_' not in name
}
