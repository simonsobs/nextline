from __future__ import annotations

import asyncio
import dataclasses
import datetime
from threading import Thread
from typing import MutableMapping  # noqa F401
from typing import Optional

from apluggy import PluginManager
from typing_extensions import TypeAlias

from .types import TraceInfo  # noqa F401
from .types import RunInfo, RunNo
from .utils import PubSub

SCRIPT_FILE_NAME = "<string>"

RunNoMap: TypeAlias = "MutableMapping[asyncio.Task | Thread, int]"
TraceNoMap: TypeAlias = "MutableMapping[asyncio.Task | Thread, int]"
TraceInfoMap: TypeAlias = "MutableMapping[int, TraceInfo]"


class Registrar:
    def __init__(self, registry: PubSub, hook: PluginManager):
        self._hook = hook
        self._registry = registry
        self._trace_info_map: TraceInfoMap = {}

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

        run_no = self._run_info.run_no
        await self._hook.ahook.on_start_run(run_no=run_no)

    async def run_end(self, result: Optional[str], exception: Optional[str]) -> None:

        run_no = self._run_info.run_no
        await self._hook.ahook.on_end_run(run_no=run_no)

        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=result,
            exception=exception,
            ended_at=datetime.datetime.utcnow(),
        )
        # TODO: check if run_no matches
        await self._registry.publish("run_info", self._run_info)
