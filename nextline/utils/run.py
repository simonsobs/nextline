import asyncio
import contextlib
import os
import signal
from collections.abc import Callable, Generator
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from logging import getLogger
from multiprocessing import Process
from multiprocessing.context import BaseContext
from typing import Any, Generic, TypeVar

from .multiprocessing_logging import MultiprocessingLogging

_T = TypeVar("_T")


@dataclass
class ExitedProcess(Generic[_T]):
    '''An object returned by RunningProcess after the process has exited.'''

    returned: _T | None
    raised: BaseException | None
    process: Process
    process_created_at: datetime
    process_exited_at: datetime


class RunningProcess(Generic[_T]):
    '''An awaitable return value of `run_in_process()`.'''

    def __init__(
        self,
        process: Process,
        task: asyncio.Task[tuple[_T | None, BaseException | None]],
    ):
        self.process = process
        self._task = task
        self.process_created_at = datetime.now(timezone.utc)
        self._process_created_at_fmt = self._format_time(self.process_created_at)
        self._log_created()

    def __repr__(self) -> str:
        ret = (
            f'<{self.__class__.__name__}'
            f' pid={self.process.pid!r}'
            f' created_at="{self._process_created_at_fmt}">'
        )
        return ret

    def _log_created(self) -> None:
        msg = f'Process ({self.process.pid}) created at {self._process_created_at_fmt}.'
        logger = getLogger()
        logger.info(msg)

    def _log_exited(self, exited_at: datetime) -> None:
        time_fmt = self._format_time(exited_at)
        exitcode = self.process.exitcode
        exit_fmt = f'{exitcode}'
        if exitcode and (name := _exitcode_to_name.get(exitcode)):
            exit_fmt = f'{exitcode} ({name})'
        pid = self.process.pid
        msg = f'Process ({pid}) exited at {time_fmt}. Exitcode: {exit_fmt}.'
        logger = getLogger(__name__)
        logger.info(msg)

    def _format_time(self, dt: datetime) -> str:
        return dt.strftime('%Y-%m-%d %H:%M:%S (%Z)')

    def interrupt(self) -> None:
        self.send_signal(signal.SIGINT)

    def send_signal(self, sig: int) -> None:
        if self.process.pid:
            os.kill(self.process.pid, sig)

    def terminate(self) -> None:
        self.process.terminate()

    def kill(self) -> None:
        self.process.kill()

    def __await__(self) -> Generator[None, None, ExitedProcess[_T]]:
        # "yield from" in "__await__": https://stackoverflow.com/a/48261042/7309855
        ret, exc = yield from self._task.__await__()
        process_exited_at = datetime.now(timezone.utc)
        self._log_exited(process_exited_at)
        return ExitedProcess(
            returned=ret,
            raised=exc,
            process=self.process,
            process_created_at=self.process_created_at,
            process_exited_at=process_exited_at,
        )


def _call_all(*funcs: Callable[[], Any] | None) -> None:
    '''Execute callables and ignore return values.

    Used to call multiple initializers in ProcessPoolExecutor.
    '''
    for func in funcs:
        if func is None:
            continue
        func()


async def run_in_process(
    func: Callable[[], _T],
    mp_context: BaseContext | None = None,
    initializer: Callable[[], None] | None = None,
    collect_logging: bool = False,
) -> RunningProcess[_T]:
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
    ...     exited = await running
    ...
    ...     return exited.returned

    >>> asyncio.run(simple_example())
    8

    '''

    process: Process | None = None
    event = asyncio.Event()

    async def _run() -> tuple[_T | None, BaseException | None]:
        nonlocal process
        nonlocal initializer

        async with contextlib.AsyncExitStack() as stack:
            if collect_logging:
                logging_initializer = await stack.enter_async_context(
                    MultiprocessingLogging(mp_context=mp_context)
                )
                initializer = partial(_call_all, logging_initializer, initializer)

            with ProcessPoolExecutor(
                max_workers=1, mp_context=mp_context, initializer=initializer
            ) as executor:
                loop = asyncio.get_running_loop()
                future = loop.run_in_executor(executor, func)
                process = list(executor._processes.values())[0]

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

    task = asyncio.create_task(_run())
    await event.wait()
    assert process
    ret = RunningProcess[_T](process=process, task=task)
    return ret


# Originally copied from
# https://github.com/python/cpython/blob/3.8/Lib/multiprocessing/process.py#L425-L429
_exitcode_to_name = {
    -signum: f'-{name}'
    for name, signum in signal.__dict__.items()
    if name[:3] == 'SIG' and '_' not in name
}
