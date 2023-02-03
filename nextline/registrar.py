from __future__ import annotations

import asyncio
import dataclasses
import datetime
from threading import Thread  # noqa F401
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
            await self._registry.publish(key, value)

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
            started_at=datetime.datetime.now(),
        )
        await self._registry.publish("run_info", self._run_info)

    async def run_end(self, result: Optional[str], exception: Optional[str]) -> None:
        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=result,
            exception=exception,
            ended_at=datetime.datetime.now(),
        )
        # TODO: check if run_no matches
        await self._registry.publish("run_info", self._run_info)
