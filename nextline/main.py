import asyncio
import linecache
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger
from typing import Any, Optional

from .continuous import Continuous
from .fsm import Machine
from .plugin import Context, build_hook, log_loaded_plugins
from .spawned import PdbCommand
from .types import (
    InitOptions,
    PromptInfo,
    PromptNo,
    PromptNotice,
    ResetOptions,
    RunInfo,
    Statement,
    StdoutInfo,
    TraceInfo,
    TraceNo,
)
from .utils import merge_aiters
from .utils.pubsub.broker import PubSub


class Nextline:
    '''Nextline allows line-by-line execution of concurrent Python scripts

    Nextline supports concurrency with threading and asyncio. It uses multiple
    instances of Pdb, one for each thread and async task.


    Parameters
    ----------
    statement : str or Path or CodeType or Callable[[], Any]
        A Python code as a str, a Path object that points to a Python script,
        a CodeType object, or a callable with no arguments. It must be
        picklable.
    run_no_start_from : int, optional
        The first run number. The default is 1.
    trace_threads : bool, optional
        The default is False. If False, trace only the main thread. If True,
        trace all threads.
    trace_modules : bool, optional
        The default is False. If False, trace only the statement. If True,
        trace imported modules as well.
    timeout_on_exit : float, optional
        The timeout in seconds to wait for the nextline to exit from the "with"
        block. The default is 3.

    '''

    def __init__(
        self,
        statement: Statement,
        run_no_start_from: int = 1,
        trace_threads: bool = False,
        trace_modules: bool = False,
        timeout_on_exit: float = 3,
    ):
        self._init_options = InitOptions(
            statement=statement,
            run_no_start_from=run_no_start_from,
            trace_threads=trace_threads,
            trace_modules=trace_modules,
        )
        self._continuous = Continuous(self)
        self._pubsub = PubSub[Any, Any]()
        self._timeout_on_exit = timeout_on_exit
        self._started = False
        self._closed = False
        self._hook = build_hook()

    def __repr__(self) -> str:
        # e.g., "<Nextline 'running'>"
        return f'<{self.__class__.__name__} {self.state!r}>'

    def register(self, plugin: Any) -> str | None:
        return self._hook.register(plugin)

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        logger = getLogger(__name__)
        logger.debug(f'self._init_options: {self._init_options}')
        log_loaded_plugins(hook=self._hook)
        context = Context(nextline=self, hook=self._hook, pubsub=self._pubsub)
        self._hook.hook.init(context=context, init_options=self._init_options)
        self._machine = Machine(context=context)
        await self._continuous.start()
        await self._machine.initialize()  # type: ignore

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._pubsub.close()
        await self._machine.close()  # type: ignore
        await self._continuous.close()

    async def __aenter__(self) -> 'Nextline':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore
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

    async def run_and_continue(self) -> None:
        '''Start the script execution in the non-interactive mode.

        Returns when the run has started.
        '''
        await self._continuous.run_and_continue()

    async def run_continue_and_wait(self, started: asyncio.Event) -> None:
        '''Start the script execution in the non-interactive mode and wait until end.

        Similar to run_and_continue() but returns when the run has finished.
        The event started is set when the run has started.
        '''
        await self._continuous.run_continue_and_wait(started)

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

    def format_exception(self) -> Optional[str]:
        '''Formatted uncaught exception from the last run'''
        return self._machine.format_exception()

    def result(self) -> Any:
        '''Return value of the last run. None unless the statement is a callable.'''
        return self._machine.result()

    async def reset(
        self,
        statement: Optional[Statement] = None,
        run_no_start_from: Optional[int] = None,
        trace_threads: Optional[bool] = None,
        trace_modules: Optional[bool] = None,
    ) -> None:
        """Prepare for the next run"""
        reset_options = ResetOptions(
            statement=statement,
            run_no_start_from=run_no_start_from,
            trace_threads=trace_threads,
            trace_modules=trace_modules,
        )
        logger = getLogger(__name__)
        logger.debug(f'reset_options: {reset_options}')
        await self._machine.reset(  # type: ignore
            reset_options=reset_options,
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
    def run_no(self) -> int:
        """The current run number"""
        return self.get("run_no")

    def subscribe_run_no(self) -> AsyncIterator[int]:
        return self.subscribe("run_no")

    @property
    def trace_ids(self) -> tuple[int, ...]:
        try:
            return self.get("trace_nos")
        except (KeyError, LookupError):
            return ()

    def subscribe_trace_ids(self) -> AsyncIterator[tuple[int, ...]]:
        return self.subscribe("trace_nos")

    def get_source(self, file_name: Optional[str] = None) -> list[str]:
        if not file_name or file_name == self._pubsub.latest("script_file_name"):
            return self.get("statement").split("\n")
        return [e.rstrip() for e in linecache.getlines(file_name)]

    def get_source_line(self, line_no: int, file_name: Optional[str] = None) -> str:
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

    def get(self, key: Any) -> Any:
        return self._pubsub.latest(key)

    def subscribe(self, key: Any, last: Optional[bool] = True) -> AsyncIterator[Any]:
        return self._pubsub.subscribe(key, last=last)

    def subscribe_stdout(self) -> AsyncIterator[StdoutInfo]:
        return self.subscribe("stdout", last=False)

    @property
    def continuous_enabled(self) -> bool:
        return self._continuous.enabled

    def subscribe_continuous_enabled(self) -> AsyncIterator[bool]:
        return self._continuous.subscribe_enabled()
