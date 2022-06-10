from __future__ import annotations

from asyncio import Task  # noqa F401
from multiprocessing import Queue
from threading import Thread  # noqa F401
import dataclasses
import datetime
import traceback
import json

from typing import TYPE_CHECKING, Any, Tuple
from typing import MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from .types import RunNo, RunInfo
from .types import TraceInfo  # noqa F401
from .utils import ExcThread

if TYPE_CHECKING:
    from .state import State

SCRIPT_FILE_NAME = "<string>"

RunNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"
TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"
TraceInfoMap: TypeAlias = "MutableMapping[int, TraceInfo]"


class Registrar:
    def __init__(self, registry: MutableMapping):
        self._registry = registry
        self._queue: Queue[Tuple[str, Any, bool]] = Queue()
        self._thread = ExcThread(target=self._relay, daemon=True)
        self._thread.start()

    @property
    def queue(self) -> Queue[Tuple[str, Any, bool]]:
        return self._queue

    def close(self):
        self._queue.put(None)
        self._thread.join()

    def _relay(self) -> None:
        while (m := self._queue.get()) is not None:
            key, value, close = m
            if close:
                try:
                    del self._registry[key]
                except KeyError:
                    pass
                continue
            self._registry[key] = value

    def script_change(self, script: str, filename: str) -> None:
        self._registry["statement"] = script
        self._registry["script_file_name"] = filename

    def state_change(self, state: State) -> None:
        self._registry["state_name"] = state.name

    def state_initialized(self, run_no: int) -> None:
        self._registry["run_no"] = run_no

    def run_start(self, run_no: RunNo) -> None:
        self._run_info = RunInfo(
            run_no=run_no,
            state="running",
            script=self._registry["statement"],
            started_at=datetime.datetime.now(),
        )
        self._registry["run_info"] = self._run_info

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
        self._registry["run_info"] = self._run_info
