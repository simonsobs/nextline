import linecache

from typing import Any, AsyncGenerator, Optional, Tuple

from .state import Machine


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

    def run(self) -> None:
        """Execute the script"""
        self.machine.run()

    async def finish(self) -> None:
        """Wait until the script execution exits"""
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

    async def subscribe_state(self) -> AsyncGenerator[str, None]:
        # wish to be able to write with "yield from" but not possible
        # https://stackoverflow.com/a/59079548/7309855
        agen = self.registry.subscribe("state_name")
        async for y in agen:
            yield y

    @property
    def run_no(self):
        """The current run number"""
        return self.registry.get("run_no")

    async def subscribe_run_no(self):
        agen = self.registry.subscribe("run_no")
        async for y in agen:
            yield y

    async def subscribe_trace_ids(self) -> AsyncGenerator[Tuple[int], None]:
        agen = self.registry.subscribe("trace_ids")
        async for y in agen:
            yield y

    async def subscribe_trace_state(self, trace_id: int):
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
