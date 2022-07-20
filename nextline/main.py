from __future__ import annotations

import linecache
from logging import getLogger

from typing import Any, AsyncIterator, Optional, Tuple

from .utils import merge_aiters
from .context import Context
from .state import Machine
from .types import PromptNo, TraceNo, StdoutInfo

from .types import RunInfo, TraceInfo, PromptInfo


class Nextline:
    """Nextline allows line-by-line execution of concurrent Python scripts

    Nextline supports concurrency with threading and asyncio. It uses multiple
    instances of Pdb, one for each thread and async task.

    Note
    ----
    The running asyncio event loop must exists when Nextline is instantiated.

    Parameters
    ----------
    statement : str
        A Python code as a string

    """

    def __init__(self, statement: str, run_no_start_from: int = 1):

        logger = getLogger(__name__)
        logger.debug(f"statement starts with {statement[:25]!r}")
        logger.debug(f"The next run number will be {run_no_start_from}")

        self._context = Context(
            run_no_start_from=run_no_start_from,
            statement=statement,
        )
        self._registry = self._context.registry
        self._q_commands = self._context.q_commands

        self._closed = False

    async def start(self) -> None:
        await self._context.start()
        self._machine = Machine(self._context)
        await self._machine.initialize()

    def __repr__(self):
        # e.g., "<Nextline 'running'>"
        return f"<{self.__class__.__name__} {self.state!r}>"

    async def close(self) -> None:
        """End gracefully"""
        if self._closed:
            return
        self._closed = True
        await self._machine.close()
        await self._context.shutdown()
        await self._registry.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()

    async def run(self) -> None:
        """Execute the script and wait until it exits"""
        await self._machine.run()
        await self._machine.finish()

    def send_pdb_command(
        self, command: str, prompt_no: int, trace_no: int
    ) -> None:
        self._q_commands.put((command, PromptNo(prompt_no), TraceNo(trace_no)))

    def interrupt(self) -> None:
        self._machine.interrupt()

    def terminate(self) -> None:
        self._machine.terminate()

    def kill(self) -> None:
        self._machine.kill()

    def exception(self) -> Optional[BaseException]:
        """Uncaught exception from the last run"""
        return self._machine.exception()

    def result(self) -> Any:
        """Return value of the last run. always None"""
        return self._machine.result()

    async def reset(
        self,
        statement: Optional[str] = None,
        run_no_start_from: Optional[int] = None,
    ) -> None:
        """Prepare for the next run"""
        await self._machine.reset(
            statement=statement,
            run_no_start_from=run_no_start_from,
        )

    @property
    def statement(self) -> str:
        """The script"""
        return self.get("statement")

    @property
    def state(self) -> str:
        """The current condition of the script execution.

        The possible values are "initialized", "running", "finished",
        "closed"
        """
        return self._machine.state_name

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
        if not file_name or file_name == self._registry.latest(
            "script_file_name"
        ):
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

    def subscribe_prompt_info(self) -> AsyncIterator[PromptInfo]:
        return self.subscribe("prompt_info")

    def subscribe_prompt_info_for(
        self, trace_no: int
    ) -> AsyncIterator[PromptInfo]:
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

    def subscribe(
        self, key, last: Optional[bool] = True
    ) -> AsyncIterator[Any]:
        return self._registry.subscribe(key, last=last)

    def subscribe_stdout(self) -> AsyncIterator[StdoutInfo]:
        return self.subscribe("stdout", last=False)
