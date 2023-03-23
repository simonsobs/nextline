from typing import Optional, Tuple

from nextline.plugin.spec import hookimpl
from nextline.spawned import OnEndTrace, OnStartTrace, RunArg
from nextline.types import RunNo, TraceNo
from nextline.utils.pubsub.broker import PubSub


class TraceNumbersRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_nos: Tuple[TraceNo, ...] = ()

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

        self._trace_nos = ()
        await self._registry.publish('trace_nos', self._trace_nos)

    @hookimpl
    async def on_start_trace(self, event: OnStartTrace) -> None:
        trace_no = event.trace_no
        self._trace_nos = self._trace_nos + (trace_no,)
        await self._registry.publish('trace_nos', self._trace_nos)

    @hookimpl
    async def on_end_trace(self, event: OnEndTrace) -> None:
        trace_no = event.trace_no
        nosl = list(self._trace_nos)
        try:
            nosl.remove(trace_no)
        except ValueError:
            return
        self._trace_nos = tuple(nosl)
        await self._registry.publish('trace_nos', self._trace_nos)
