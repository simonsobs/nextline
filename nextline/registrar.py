from __future__ import annotations

from asyncio import Task  # noqa F401
from threading import Thread  # noqa F401
import dataclasses
import datetime
from itertools import count
import traceback
import json
from weakref import WeakKeyDictionary

from typing import TYPE_CHECKING
from typing import MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from .types import RunInfo, TraceInfo, PromptInfo
from .utils import ThreadTaskIdComposer
from .utils.func import current_task_or_thread

if TYPE_CHECKING:
    from .state import State

SCRIPT_FILE_NAME = "<string>"

RunNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"
TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"


class Registrar:
    def __init__(self, registry: MutableMapping, run_no_start_from: int):
        self._registry = registry
        self._run_no_count = count(run_no_start_from).__next__
        self._run_no_map: RunNoMap = WeakKeyDictionary()
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._registry["run_no_map"] = self._run_no_map
        self._registry["trace_no_map"] = self._trace_no_map
        self._trace_id_factory = ThreadTaskIdComposer()

    def reset_run_no_count(self, run_no_start_from: int) -> None:
        self._run_no_count = count(run_no_start_from).__next__

    def script_change(self, script: str, filename: str) -> None:
        self._registry["statement"] = script
        self._registry["script_file_name"] = filename

    def state_change(self, state: State) -> None:
        self._registry["state_name"] = state.name
        if state.name == "initialized":
            self.state_initialized()
            return
        if state.name == "running":
            self.run_start()
            return
        if state.name == "finished":
            self.run_end(state=state)
            return

    def state_initialized(self) -> None:
        self._registry["run_no"] = self._run_no_count()
        self._trace_id_factory.reset()

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

    def trace_start(self, trace_no) -> TraceInfo:

        nos = (self._registry.get("trace_nos") or ()) + (trace_no,)
        self._registry["trace_nos"] = nos

        run_no: int = self._registry["run_no"]

        self._registry[f"prompt_info_{trace_no}"] = PromptInfo(
            run_no=run_no,
            trace_no=trace_no,
            prompt_no=-1,
            open=False,
        )

        task_or_thread = current_task_or_thread()
        self._run_no_map[task_or_thread] = run_no
        self._trace_no_map[task_or_thread] = trace_no

        thread_task_id = self._trace_id_factory()

        trace_info = TraceInfo(
            run_no=run_no,
            trace_no=trace_no,
            thread_no=thread_task_id.thread_no,
            task_no=thread_task_id.task_no,
            state="running",
            started_at=datetime.datetime.now(),
        )
        print(f"trace_start({trace_info})")
        self._registry["trace_info"] = trace_info
        return trace_info

    def trace_end(self, trace_info: TraceInfo):
        print(f"trace_end({trace_info})")
        self._registry["trace_info"] = trace_info
