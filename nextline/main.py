import asyncio
import linecache
import reprlib
from contextlib import asynccontextmanager
from logging import getLogger
from pathlib import Path
from types import CodeType
from typing import Any, AsyncIterator, Callable, Optional, Tuple, Union

from .fsm import Machine
from .spawned import PdbCommand
from .types import (
    PromptInfo,
    PromptNo,
    PromptNotice,
    RunInfo,
    StdoutInfo,
    TraceInfo,
    TraceNo,
)
from .utils import merge_aiters


class Nextline:
    '''Nextline allows line-by-line execution of concurrent Python scripts

    Nextline supports concurrency with threading and asyncio. It uses multiple
    instances of Pdb, one for each thread and async task.


    Parameters
    ----------
    statement : str or Path or CodeType or Callable[[], Any]
        Typically, a Python code as a str. However, if a statement is a str
        that is a path to an existing file, it is considered as a path to a
        Python script. A Path object is also considered as a path to a Python
        script. Alternatively, a statement can be a CodeType object or a
        callable with no arguments. A statement must be picklable.
    run_no_start_from : int, optional
        The first run number. The default is 1.
    timeout_on_exit : float, optional
        The timeout in seconds to wait for the nextline to exit from the "with"
        block. The default is 3.

    '''

    def __init__(
        self,
        statement: Union[str, Path, CodeType, Callable[[], Any]],
        run_no_start_from: int = 1,
        timeout_on_exit: float = 3,
    ):

        logger = getLogger(__name__)
        logger.debug(f'statement: {reprlib.repr(statement)}')
        logger.debug(f"The run number starts from {run_no_start_from}")

        self._machine = Machine(
            run_no_start_from=run_no_start_from,
            statement=statement,
        )
        self._timeout_on_exit = timeout_on_exit
        self._registry = self._machine.registry

        self._started = False
        self._closed = False

    def __repr__(self):
        # e.g., "<Nextline 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        await self._machine.initialize()  # type: ignore

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._machine.close()  # type: ignore

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await asyncio.wait_for(self.close(), timeout=self._timeout_on_exit)

    async def run(self) -> None:
        '''Start the script execution.'''
        await self._machine.run()  # type: ignore

    @asynccontextmanager
    async def run_session(self) -> AsyncIterator['Nextline']:
        '''Yield when the script execution is started and exit when it has finished.'''
        await self._machine.run()  # type: ignore
        try:
            yield self
        finally:
            await self._machine.wait()

    async def send_pdb_command(
        self, command: str, prompt_no: int, trace_no: int
    ) -> None:
        logger = getLogger(__name__)
        logger.debug(f'send_pdb_command({command!r}, {prompt_no!r}, {trace_no!r})')
        item = PdbCommand(
            trace_no=TraceNo(trace_no),
            prompt_no=PromptNo(prompt_no),
            command=command,
        )
        await self._machine.send_command(item)

    async def interrupt(self) -> None:
        await self._machine.interrupt()

    async def terminate(self) -> None:
        await self._machine.terminate()

    async def kill(self) -> None:
        await self._machine.kill()  # type: ignore

    def exception(self) -> Optional[BaseException]:
        """Uncaught exception from the last run"""
        return self._machine.exception()

    def result(self) -> Any:
        '''Return value of the last run. None unless the statement is a callable.'''
        return self._machine.result()

    async def reset(
        self,
        statement: Union[str, Path, CodeType, Callable[[], Any], None] = None,
        run_no_start_from: Optional[int] = None,
    ) -> None:
        """Prepare for the next run"""
        await self._machine.reset(  # type: ignore
            statement=statement,
            run_no_start_from=run_no_start_from,
        )

    @property
    def statement(self) -> str:
        """The script"""
        return self.get("statement")

    @property
    def state(self) -> Optional[str]:
        """The current condition of the script execution.

        The possible values are "initialized", "running", "finished",
        "closed"
        """
        try:
            return self._machine.state  # type: ignore
        except AttributeError:
            return None

    def subscribe_state(self) -> AsyncIterator[str]:
        return self.subscribe("state_name")

    @property
    def run_no(self):
        """The current run number"""
        return self.get("run_no")

    def subscribe_run_no(self) -> AsyncIterator[int]:
        return self.subscribe("run_no")

    def subscribe_trace_ids(self) -> AsyncIterator[Tuple[int]]:
        return self.subscribe("trace_nos")

    def get_source(self, file_name=None):
        if not file_name or file_name == self._registry.latest("script_file_name"):
            return self.get("statement").split("\n")
        return [e.rstrip() for e in linecache.getlines(file_name)]

    def get_source_line(self, line_no, file_name=None):
        """
        based on linecache.getline()
        https://github.com/python/cpython/blob/v3.9.5/Lib/linecache.py#L26
        """
        lines = self.get_source(file_name)
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ""

    def subscribe_run_info(self) -> AsyncIterator[RunInfo]:
        return self.subscribe("run_info")

    def subscribe_trace_info(self) -> AsyncIterator[TraceInfo]:
        return self.subscribe("trace_info")

    def prompts(self) -> AsyncIterator[PromptNotice]:
        '''Yield for each prompt. Return when the run ends.'''
        return self.subscribe('prompt_notice')

    def subscribe_prompt_info(self) -> AsyncIterator[PromptInfo]:
        return self.subscribe("prompt_info")

    def subscribe_prompt_info_for(self, trace_no: int) -> AsyncIterator[PromptInfo]:
        return self.subscribe(f"prompt_info_{trace_no}")

        # Alternative implementation under development
        # return self._subscribe_prompt_info_for(trace_no)

    async def _subscribe_prompt_info_for(
        self, trace_no: int
    ) -> AsyncIterator[PromptInfo]:

        merged = merge_aiters(
            self.subscribe_prompt_info(),
            self.subscribe_trace_info(),
        )
        async for _, info in merged:
            if not info.trace_no == trace_no:  # type: ignore
                continue
            if isinstance(info, TraceInfo):
                if info.trace_no == trace_no:
                    if info.state == "finished":
                        break
                continue
            assert isinstance(info, PromptInfo)
            yield info

    def get(self, key) -> Any:
        return self._registry.latest(key)

    def subscribe(self, key, last: Optional[bool] = True) -> AsyncIterator[Any]:
        return self._registry.subscribe(key, last=last)

    def subscribe_stdout(self) -> AsyncIterator[StdoutInfo]:
        return self.subscribe("stdout", last=False)
