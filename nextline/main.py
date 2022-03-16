from __future__ import annotations

import sys
import io
import datetime
import linecache

from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Optional,
    Tuple,
    TextIO,
)


from .state import Machine
from .utils import QueueDist, current_task_or_thread
from .types import StdoutInfo

if TYPE_CHECKING:
    from .pdb.proxy import PdbCIState
    from .types import RunInfo, TraceInfo, PromptInfo
    from .utils import SubscribableDict


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

    def __init__(self, statement, run_no_start_from: int = 1):
        self.machine = Machine(statement, run_no_start_from)
        self.registry = self.machine.registry
        self._stdout = sys.stdout = IOSubscription(sys.stdout, self.registry)

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
        return self.get("statement")

    @property
    def state(self) -> str:
        """The current condition of the script execution.

        The possible values are "initialized", "running", "exited", "finished",
        "closed"
        """
        return self.machine.state_name

    def subscribe_state(self) -> AsyncGenerator[str, None]:
        return self.subscribe("state_name")

    @property
    def run_no(self):
        """The current run number"""
        return self.get("run_no")

    def subscribe_run_no(self) -> AsyncGenerator[int, None]:
        return self.subscribe("run_no")

    def subscribe_trace_ids(self) -> AsyncGenerator[Tuple[int], None]:
        return self.subscribe("trace_nos")

    async def subscribe_prompting(
        self,
        trace_id: int,
    ) -> AsyncGenerator[PdbCIState, None]:
        agen = self.subscribe(trace_id)
        async for y in agen:
            if y is None:
                continue
            yield y

    def send_pdb_command(self, trace_id: int, command: str):
        self.machine.send_pdb_command(trace_id, command)

    def get_source(self, file_name=None):
        if not file_name or file_name == self.registry.get("script_file_name"):
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

    def subscribe_run_info(self) -> AsyncGenerator[RunInfo, None]:
        return self.subscribe("run_info")

    def subscribe_trace_info(self) -> AsyncGenerator[TraceInfo, None]:
        return self.subscribe("trace_info")

    def subscribe_prompt_info(self) -> AsyncGenerator[PromptInfo, None]:
        return self.subscribe("prompt_info")

    def get(self, key) -> Any:
        return self.registry.get(key)

    def subscribe(self, key) -> AsyncGenerator[Any, None]:
        return self.registry.subscribe(key)

    def subscribe_stdout(self) -> AsyncGenerator[StdoutInfo, None]:
        return self._stdout.subscribe()


AGenDatetimeStr = AsyncGenerator[Tuple[datetime.datetime, str], None]


class IOSubscription(io.TextIOWrapper):
    def __init__(self, src: TextIO, registry: SubscribableDict):
        """Make output stream subscribable

        The src needs to be replaced with the instance of this class. For
        example, if the src is stdout,
            sys.stdout = IOSubscription(sys.stdout)

        NOTE: The code on the logic about the buffer copied from
        https://github.com/alphatwirl/atpbar/blob/894a7e0b4d81aa7b/atpbar/stream.py#L54
        """
        self.registry = registry
        self._queue = QueueDist()
        self._src = src
        self._buffer = ""

        self._id_composer = registry["trace_id_factory"]  # type: ignore
        self._run_no_map = registry["run_no_map"]  # type: ignore
        self._trace_no_map = registry["trace_no_map"]  # type: ignore

    def write(self, s: str) -> int:

        ret = self._src.write(s)
        # TypeError if s isn't str as long as self._src is sys.stdout or
        # sys.stderr.

        if not self._id_composer.has_id():
            return ret

        self._buffer += s
        if s.endswith("\n"):
            self.flush()
        return ret

    def flush(self):
        if not self._buffer:
            return
        if not self._id_composer.has_id():
            return
        key = current_task_or_thread()
        if not (run_no := self._run_no_map.get(key)):
            return
        if not (trace_no := self._trace_no_map.get(key)):
            return
        now = datetime.datetime.now()
        info = StdoutInfo(
            run_no=run_no,
            trace_no=trace_no,
            text=self._buffer,
            written_at=now,
        )
        # print(info, file=sys.stderr)
        self._queue.put(info)
        self._buffer = ""

    async def subscribe(self):
        async for y in self._queue.subscribe():  # type: ignore
            yield y
