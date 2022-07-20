from __future__ import annotations

import asyncio
from threading import Thread  # noqa F401
import dataclasses
import datetime

from typing import TYPE_CHECKING, Optional
from typing import MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from .types import RunNo, RunInfo
from .types import TraceInfo  # noqa F401
from .utils import to_thread, PubSub

if TYPE_CHECKING:
    from .state import State
    from .process.run import QueueRegistry

SCRIPT_FILE_NAME = "<string>"

RunNoMap: TypeAlias = "MutableMapping[asyncio.Task | Thread, int]"
TraceNoMap: TypeAlias = "MutableMapping[asyncio.Task | Thread, int]"
TraceInfoMap: TypeAlias = "MutableMapping[int, TraceInfo]"


class Registrar:
    def __init__(self, registry: PubSub, queue: QueueRegistry):
        self._registry = registry
        self._queue = queue
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
            await self._registry.publish(key, value)

    async def script_change(self, script: str, filename: str) -> None:
        await self._registry.publish("statement", script)
        await self._registry.publish("script_file_name", filename)

    async def state_change(self, state: State) -> None:
        await self._registry.publish("state_name", state.name)

    async def state_initialized(self, run_no: int) -> None:
        await self._registry.publish("run_no", run_no)

    async def run_start(self, run_no: RunNo) -> None:
        self._run_info = RunInfo(
            run_no=run_no,
            state="running",
            script=self._registry.latest("statement"),
            started_at=datetime.datetime.now(),
        )
        await self._registry.publish("run_info", self._run_info)

    async def run_end(
        self, result: Optional[str], exception: Optional[str]
    ) -> None:
        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=result,
            exception=exception,
            ended_at=datetime.datetime.now(),
        )
        # TODO: check if run_no matches
        await self._registry.publish("run_info", self._run_info)
