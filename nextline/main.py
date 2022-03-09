from __future__ import annotations

import linecache

from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional, Tuple

from .state import Machine

if TYPE_CHECKING:
    from .pdb.proxy import PdbCIState


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

    def __init__(self, statement):
        self.machine = Machine(statement)
        self.registry = self.machine.registry

    def __repr__(self):
        # e.g., "<Nextline 'running'>"
        return f"<{self.__class__.__name__} {self.state!r}>"

    async def run(self) -> None:
        """Execute the script and wait until it exits"""
        self.machine.run()
        await self.machine.finish()

    def exception(self) -> Optional[Exception]:
        """Uncaught exception from the last run"""
        return self.machine.exception()

    def result(self) -> Any:
        """Return value of the last run. always None"""
        return self.machine.result()

    def reset(self, statement=None) -> None:
        """Prepare for the next run"""
        self.machine.reset(statement=statement)

    async def close(self) -> None:
        """End gracefully"""
        await self.machine.close()

    @property
    def statement(self) -> str:
        """The script"""
        return self.registry.get("statement")

    @property
    def state(self) -> str:
        """The current condition of the script execution.

        The possible values are "initialized", "running", "exited", "finished",
        "closed"
        """
        return self.machine.state_name

    def subscribe_state(self) -> AsyncGenerator[str, None]:
        return self.registry.subscribe("state_name")

    @property
    def run_no(self):
        """The current run number"""
        return self.registry.get("run_no")

    def subscribe_run_no(self) -> AsyncGenerator[int, None]:
        return self.registry.subscribe("run_no")

    def subscribe_trace_ids(self) -> AsyncGenerator[Tuple[int], None]:
        return self.registry.subscribe("trace_ids")

    async def subscribe_prompting(
        self,
        trace_id: int,
    ) -> AsyncGenerator[PdbCIState, None]:
        agen = self.registry.subscribe(trace_id)
        async for y in agen:
            if y is None:
                continue
            yield y

    def send_pdb_command(self, trace_id: int, command: str):
        self.machine.send_pdb_command(trace_id, command)

    def get_source(self, file_name=None):
        if not file_name or file_name == self.registry.get("script_file_name"):
            return self.registry.get("statement").split("\n")
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
