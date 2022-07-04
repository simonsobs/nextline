from __future__ import annotations

import asyncio
from threading import Thread  # noqa F401
import dataclasses
import datetime
import traceback
import json

from typing import TYPE_CHECKING
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
        self._queue.put(None)
        await self._task

    async def _relay(self) -> None:
        while (m := await to_thread(self._queue.get)) is not None:
            key, value, close = m
            if close:
                await self._registry.end(key)
                continue
            self._registry.publish(key, value)

    def script_change(self, script: str, filename: str) -> None:
        self._registry.publish("statement", script)
        self._registry.publish("script_file_name", filename)

    def state_change(self, state: State) -> None:
        self._registry.publish("state_name", state.name)

    def state_initialized(self, run_no: int) -> None:
        self._registry.publish("run_no", run_no)

    def run_start(self, run_no: RunNo) -> None:
        self._run_info = RunInfo(
            run_no=run_no,
            state="running",
            script=self._registry.latest("statement"),
            started_at=datetime.datetime.now(),
        )
        self._registry.publish("run_info", self._run_info)

    def run_end(self, state: State) -> None:
        exc = state.exception()
        ret = state.result() if not exc else None
        if exc:
            fmt_exc = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
        else:
            ret = json.dumps(ret)
            fmt_exc = None
        self._run_info = dataclasses.replace(
            self._run_info,
            state="finished",
            result=ret,
            exception=fmt_exc,
            ended_at=datetime.datetime.now(),
        )
        # TODO: check if run_no matches
        self._registry.publish("run_info", self._run_info)
