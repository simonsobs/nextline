from typing import Optional

from nextline.plugin.spec import hookimpl
from nextline.spawned import OnWriteStdout, RunArg
from nextline.types import RunNo, StdoutInfo
from nextline.utils.pubsub.broker import PubSub


class StdoutRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None

    @hookimpl
    def init(self, registry: PubSub) -> None:
        self._registry = registry

    @hookimpl
    async def on_initialize_run(self, run_arg: RunArg) -> None:
        self._run_no = run_arg.run_no
        self._trace_nos = ()

    @hookimpl
    async def on_end_run(self) -> None:
        self._run_no = None

    @hookimpl
    async def on_write_stdout(self, event: OnWriteStdout) -> None:
        assert self._run_no is not None
        stdout_info = StdoutInfo(
            run_no=self._run_no,
            trace_no=event.trace_no,
            text=event.text,
            written_at=event.written_at,
        )
        await self._registry.publish('stdout', stdout_info)
