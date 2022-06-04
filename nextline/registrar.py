from __future__ import annotations

from asyncio import Task  # noqa F401
from threading import Thread  # noqa F401
import dataclasses
import datetime
import traceback
import json
from weakref import WeakKeyDictionary

from typing import TYPE_CHECKING
from typing import MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from .utils import SubscribableDict
from .types import RunInfo

if TYPE_CHECKING:
    from .state import State

SCRIPT_FILE_NAME = "<string>"

RunNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"
TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"


class Registrar:
    def __init__(self, registry: SubscribableDict):
        self._registry = registry
        self._run_no_map: RunNoMap = WeakKeyDictionary()
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._registry["run_no_map"] = self._run_no_map
        self._registry["trace_no_map"] = self._trace_no_map

    def script_change(self, script: str, filename: str) -> None:
        self._registry["statement"] = script
        self._registry["script_file_name"] = filename

    def state_change(self, state: State) -> None:
        self._registry["state_name"] = state.name
        if state.name == "running":
            self.run_start()
            return
        if state.name == "finished":
            self.run_end(state=state)
            return

    def run_start(self) -> None:
        self._run_info = RunInfo(
            run_no=self._registry["run_no"],
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
                traceback.format_exception(
                    type(exc), exc, exc.__traceback__
                )
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
