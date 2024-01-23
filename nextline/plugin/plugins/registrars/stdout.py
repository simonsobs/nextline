from typing import Optional

from nextline.events import OnWriteStdout
from nextline.plugin.spec import Context, hookimpl
from nextline.types import RunNo, StdoutInfo


class StdoutRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None

    @hookimpl
    async def on_write_stdout(self, context: Context, event: OnWriteStdout) -> None:
        assert context.run_arg
        stdout_info = StdoutInfo(
            run_no=context.run_arg.run_no,
            trace_no=event.trace_no,
            text=event.text,
            written_at=event.written_at,
        )
        await context.pubsub.publish('stdout', stdout_info)
