from __future__ import annotations

from asyncio import Task  # noqa F401
from threading import Thread  # noqa F401
import dataclasses
import datetime
import traceback
import json
from weakref import WeakKeyDictionary

from typing import TYPE_CHECKING, Tuple
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
TraceInfoMap: TypeAlias = "MutableMapping[int, TraceInfo]"


class Registrar:
    def __init__(self, registry: MutableMapping):
        self._registry = registry
        self._run_no_map: RunNoMap = WeakKeyDictionary()
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._registry["run_no_map"] = self._run_no_map
        self._registry["trace_no_map"] = self._trace_no_map
        self._trace_id_factory = ThreadTaskIdComposer()
        self._trace_info_map: TraceInfoMap = {}

    def script_change(self, script: str, filename: str) -> None:
        self._registry["statement"] = script
        self._registry["script_file_name"] = filename

    def state_change(self, state: State) -> None:
        self._registry["state_name"] = state.name

    def state_initialized(self, run_no: int) -> None:
        self._registry["run_no"] = run_no
        self._trace_id_factory.reset()

    def run_start(self, run_no: int) -> None:
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
        self._trace_info_map.clear()

    def trace_start(self, trace_no) -> None:
        run_no: int = self._registry["run_no"]

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
        self._trace_info_map[trace_no] = trace_info
        self.put_trace_info(trace_info)

    def trace_end(self, trace_no):
        trace_info = self._trace_info_map[trace_no]

        trace_info = dataclasses.replace(
            trace_info,
            state="finished",
            ended_at=datetime.datetime.now(),
        )

        self.put_trace_info(trace_info)

    def put_trace_nos(self, trace_nos: Tuple[int, ...]) -> None:
        self._registry["trace_nos"] = trace_nos

    def put_trace_info(self, trace_info: TraceInfo) -> None:
        self._registry["trace_info"] = trace_info

    def put_prompt_info(self, prompt_info: PromptInfo) -> None:
        self._registry["prompt_info"] = prompt_info

    def put_prompt_info_for_trace(
        self, trace_no: int, prompt_info: PromptInfo
    ) -> None:
        key = f"prompt_info_{trace_no}"
        self._registry[key] = prompt_info

    def end_prompt_info_for_trace(self, trace_no: int) -> None:
        key = f"prompt_info_{trace_no}"
        try:
            del self._registry[key]
        except KeyError:
            pass
