import asyncio
import dataclasses
import datetime
import time
from typing import Dict, Optional, Tuple

from apluggy import PluginManager

from nextline.spawned import OnEndTrace, OnStartTrace
from nextline.spec import hookimpl
from nextline.types import RunNo, TraceInfo, TraceNo
from nextline.utils.pubsub.broker import PubSub

# from rich import print


class TraceNumbersRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_nos: Tuple[TraceNo, ...] = ()

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._trace_nos = ()

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        self._run_no = None

        up_to = 0.01
        start = time.process_time()
        while self._trace_nos and time.process_time() - start < up_to:
            # on_end_trace() has not been called yet for all traces
            await asyncio.sleep(0)

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
            # on_end_run() might have already been called
            return
        self._trace_nos = tuple(nosl)
        await self._registry.publish('trace_nos', self._trace_nos)


class TraceInfoRegistrar:
    def __init__(self) -> None:
        self._run_no: Optional[RunNo] = None
        self._trace_info_map: Dict[TraceNo, TraceInfo] = {}

    @hookimpl
    def init(self, hook: PluginManager, registry: PubSub) -> None:
        self._hook = hook
        self._registry = registry

    @hookimpl
    async def on_start_run(self, run_no: RunNo) -> None:
        self._run_no = run_no
        self._trace_info_map = {}

    @hookimpl
    async def on_end_run(self, run_no: RunNo) -> None:
        assert self._run_no == run_no
        self._run_no = None

        up_to = 0.05
        start = time.process_time()
        while self._trace_info_map and time.process_time() - start < up_to:
            # on_end_trace() has not been called yet for all traces
            await asyncio.sleep(0)

        while self._trace_info_map:
            # the process might have been killed.
            _, trace_info = self._trace_info_map.popitem()
            trace_info_end = dataclasses.replace(
                trace_info,
                state='finished',
                ended_at=datetime.datetime.utcnow(),
            )
            await self._registry.publish('trace_info', trace_info_end)

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
