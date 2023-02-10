from __future__ import annotations

import asyncio
import dataclasses
import datetime
from threading import Thread
from typing import MutableMapping  # noqa F401
from typing import TYPE_CHECKING, Optional

from typing_extensions import TypeAlias

from .types import TraceInfo  # noqa F401
from .types import RunInfo, RunNo
from .utils import PubSub, to_thread

if TYPE_CHECKING:
    from .process.run import QueueRegistry

SCRIPT_FILE_NAME = "<string>"

RunNoMap: TypeAlias = "MutableMapping[asyncio.Task | Thread, int]"
TraceNoMap: TypeAlias = "MutableMapping[asyncio.Task | Thread, int]"
TraceInfoMap: TypeAlias = "MutableMapping[int, TraceInfo]"


class Registrar:
    def __init__(self, registry: PubSub, queue: QueueRegistry):
        self._registry = registry
        self._queue = queue
        self._trace_info_map: TraceInfoMap = {}

    async def open(self):
        self._task = asyncio.create_task(self._relay())

    async def close(self):
        await to_thread(self._queue.put, None)
        await self._task

    async def _relay(self) -> None:
        while (m := await to_thread(self._queue.get)) is not None:
            key, value, close = m
            if close:
                await self._registry.end(key)
                continue
            if key == 'trace_info':
                assert isinstance(value, TraceInfo)
                self._trace_info_map[value.trace_no] = value
            await self._registry.publish(key, value)

    async def _end_traces(self) -> None:
        # In case the process is terminated or killed.
        for trace_no in self._registry.latest('trace_nos'):
            key = f'prompt_info_{trace_no}'
            if key in self._registry._queue:
                await self._registry.end(key)
            trace_info = self._trace_info_map[trace_no]
            if trace_info.state == "running":
                trace_info = dataclasses.replace(
                    trace_info,
                    state="finished",
                    ended_at=datetime.datetime.utcnow(),
                )
                await self._registry.publish('trace_info', trace_info)
        await self._registry.publish('trace_nos', tuple())
        # print({k: v._last_item for k, v in self._registry._queue.items()})

    async def script_change(self, script: str, filename: str) -> None:
        await self._registry.publish("statement", script)
        await self._registry.publish("script_file_name", filename)

    async def state_change(self, state_name: str) -> None:
        await self._registry.publish("state_name", state_name)

    async def state_initialized(self, run_no: int) -> None:
        await self._registry.publish("run_no", run_no)

    async def run_initialized(self, run_no: RunNo) -> None:
        self._run_info = RunInfo(
            run_no=run_no,
            state="initialized",
            script=self._registry.latest("statement"),
        )
        await self._registry.publish("run_info", self._run_info)

    async def run_start(self) -> None:
        self._run_info = dataclasses.replace(
            self._run_info,
            state="running",
            started_at=datetime.datetime.utcnow(),
        )
        await self._registry.publish("run_info", self._run_info)

    async def run_end(self, result: Optional[str], exception: Optional[str]) -> None:
        await self._end_traces()
        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=result,
            exception=exception,
            ended_at=datetime.datetime.utcnow(),
        )
        # TODO: check if run_no matches
        await self._registry.publish("run_info", self._run_info)
