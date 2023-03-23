import dataclasses
import datetime
from typing import Dict, Optional

from nextline.plugin.spec import hookimpl
from nextline.spawned import OnEndTrace, OnStartTrace, RunArg
from nextline.types import RunNo, TraceInfo, TraceNo
from nextline.utils.pubsub.broker import PubSub


class TraceInfoRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_info_map: Dict[TraceNo, TraceInfo] = {}

    @hookimpl
    def init(self, registry: PubSub) -> None:
        self._registry = registry

    @hookimpl
    async def on_initialize_run(self, run_arg: RunArg) -> None:
        self._run_no = run_arg.run_no
        self._trace_info_map = {}

    @hookimpl
    async def on_end_run(self) -> None:
        while self._trace_info_map:
            # the process might have been killed.
            _, trace_info = self._trace_info_map.popitem()
            trace_info_end = dataclasses.replace(
                trace_info,
                state='finished',
                ended_at=datetime.datetime.utcnow(),
            )
            await self._registry.publish('trace_info', trace_info_end)
        self._run_no = None

    @hookimpl
    async def on_start_trace(self, event: OnStartTrace) -> None:
        assert self._run_no is not None
        trace_info = TraceInfo(
            run_no=self._run_no,
            trace_no=event.trace_no,
            thread_no=event.thread_no,
            task_no=event.task_no,
            state='running',
            started_at=event.started_at,
        )
        self._trace_info_map[event.trace_no] = trace_info
        await self._registry.publish('trace_info', trace_info)

    @hookimpl
    async def on_end_trace(self, event: OnEndTrace) -> None:
        trace_info = self._trace_info_map.pop(event.trace_no, None)
        if trace_info is None:
            # on_end_run() might have already been called
            return
        trace_info_end = dataclasses.replace(
            trace_info,
            state='finished',
            ended_at=event.ended_at,
        )
        await self._registry.publish('trace_info', trace_info_end)
