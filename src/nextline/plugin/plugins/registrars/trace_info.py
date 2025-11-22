import dataclasses
import datetime

from nextline.events import OnEndTrace, OnStartTrace
from nextline.plugin.spec import Context, hookimpl
from nextline.types import TraceInfo, TraceNo


class TraceInfoRegistrar:
    def __init__(self) -> None:
        self._trace_info_map = dict[TraceNo, TraceInfo]()

    @hookimpl
    async def on_initialize_run(self) -> None:
        self._trace_info_map = {}

    @hookimpl
    async def on_end_run(self, context: Context) -> None:
        while self._trace_info_map:
            # the process might have been killed.
            _, trace_info = self._trace_info_map.popitem()
            trace_info_end = dataclasses.replace(
                trace_info,
                state='finished',
                ended_at=datetime.datetime.utcnow(),
            )
            await context.pubsub.publish('trace_info', trace_info_end)

    @hookimpl
    async def on_start_trace(self, context: Context, event: OnStartTrace) -> None:
        assert context.run_arg
        trace_info = TraceInfo(
            run_no=context.run_arg.run_no,
            trace_no=event.trace_no,
            thread_no=event.thread_no,
            task_no=event.task_no,
            state='running',
            started_at=event.started_at,
        )
        self._trace_info_map[event.trace_no] = trace_info
        await context.pubsub.publish('trace_info', trace_info)

    @hookimpl
    async def on_end_trace(self, context: Context, event: OnEndTrace) -> None:
        trace_info = self._trace_info_map.pop(event.trace_no, None)
        if trace_info is None:
            # on_end_run() might have already been called
            return
        trace_info_end = dataclasses.replace(
            trace_info,
            state='finished',
            ended_at=event.ended_at,
        )
        await context.pubsub.publish('trace_info', trace_info_end)
