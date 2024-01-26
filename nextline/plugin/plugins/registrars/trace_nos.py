from nextline.events import OnEndTrace, OnStartTrace
from nextline.plugin.spec import Context, hookimpl
from nextline.types import TraceNo


class TraceNumbersRegistrar:
    def __init__(self) -> None:
        self._trace_nos: tuple[TraceNo, ...] = ()

    @hookimpl
    async def on_initialize_run(self) -> None:
        self._trace_nos = ()

    @hookimpl
    async def on_end_run(self, context: Context) -> None:
        self._trace_nos = ()
        await context.pubsub.publish('trace_nos', self._trace_nos)

    @hookimpl
    async def on_start_trace(self, context: Context, event: OnStartTrace) -> None:
        trace_no = event.trace_no
        self._trace_nos = self._trace_nos + (trace_no,)
        await context.pubsub.publish('trace_nos', self._trace_nos)

    @hookimpl
    async def on_end_trace(self, context: Context, event: OnEndTrace) -> None:
        trace_no = event.trace_no
        nosl = list(self._trace_nos)
        try:
            nosl.remove(trace_no)
        except ValueError:
            return
        self._trace_nos = tuple(nosl)
        await context.pubsub.publish('trace_nos', self._trace_nos)
