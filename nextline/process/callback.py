from __future__ import annotations

import os
from asyncio import Task
import threading
from threading import Thread
from weakref import WeakKeyDictionary
import datetime
import dataclasses

from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, Set
from typing import Dict, MutableMapping  # noqa F401
from typing_extensions import TypeAlias
from types import FrameType

from ..types import RunNo, TraceNo, PromptNo, TraceInfo, PromptInfo, StdoutInfo
from ..utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)
from .io import peek_stdout_by_task_and_thread

if TYPE_CHECKING:
    from .pdb.proxy import PdbInterface
    from .run import QueueRegistry

TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, TraceNo]"
TraceInfoMap: TypeAlias = "Dict[TraceNo, TraceInfo]"
PromptInfoMap: TypeAlias = "Dict[Tuple[TraceNo, PromptNo], PromptInfo]"
PdbIMap: TypeAlias = "Dict[TraceNo, PdbInterface]"


class Callback:
    def __init__(
        self,
        run_no: RunNo,
        registrar: RegistrarProxy,
        modules_to_trace: Set[str],
    ):
        self._run_no = run_no
        self._registrar = registrar
        self._modules_to_trace = modules_to_trace
        self._trace_nos: Tuple[TraceNo, ...] = ()
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._trace_id_factory = ThreadTaskIdComposer()
        self._trace_info_map: TraceInfoMap = {}
        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self.task_or_thread_end
        )
        self._tasks_and_threads: Set[Task | Thread] = set()
        self._prompt_info_map: PromptInfoMap = {}
        self._pdbi_map: PdbIMap = {}
        self._to_canonic = ToCanonic()
        self._entering_thread: Optional[Thread] = None
        self._last_prompt_frame_map: Dict[TraceNo, FrameType] = {}
        self._current_trace_call_map: Dict[
            TraceNo, Tuple[FrameType, str, Any]
        ] = {}

    def task_or_thread_start(
        self, trace_no: TraceNo, pdbi: PdbInterface
    ) -> None:
        self.trace_start(trace_no, pdbi)

        task_or_thread = current_task_or_thread()
        self._trace_no_map[task_or_thread] = trace_no

        if task_or_thread is not self._entering_thread:
            self._thread_task_done_callback.register(task_or_thread)

        self._tasks_and_threads.add(task_or_thread)

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self.trace_end(trace_no)

    def trace_start(self, trace_no: TraceNo, pdbi: PdbInterface):
        self._pdbi_map[trace_no] = pdbi

        # TODO: Putting a prompt info for now because otherwise tests get stuck
        # sometimes for an unknown reason. Need to investigate
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
        )
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

        self._trace_nos = self._trace_nos + (trace_no,)
        self._registrar.put_trace_nos(self._trace_nos)

        thread_task_id = self._trace_id_factory()

        trace_info = TraceInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            thread_no=thread_task_id.thread_no,
            task_no=thread_task_id.task_no,
            state="running",
            started_at=datetime.datetime.now(),
        )
        self._trace_info_map[trace_no] = trace_info
        self._registrar.put_trace_info(trace_info)

    def trace_end(self, trace_no: TraceNo):
        self._registrar.end_prompt_info_for_trace(trace_no)
        self._pdbi_map.pop(trace_no).close()

        nosl = list(self._trace_nos)
        nosl.remove(trace_no)
        self._trace_nos = tuple(nosl)
        self._registrar.put_trace_nos(self._trace_nos)

        trace_info = self._trace_info_map[trace_no]

        trace_info = dataclasses.replace(
            trace_info,
            state="finished",
            ended_at=datetime.datetime.now(),
        )

        self._registrar.put_trace_info(trace_info)

    def trace_call_start(
        self,
        trace_no: TraceNo,
        trace_args: Tuple[FrameType, str, Any],
    ):
        self._current_trace_call_map[trace_no] = trace_args

    def trace_call_end(self, trace_no: TraceNo):
        frame, event, _ = self._current_trace_call_map[trace_no]
        file_name = self._to_canonic(frame.f_code.co_filename)
        line_no = frame.f_lineno

        if frame is not self._last_prompt_frame_map.get(trace_no):
            return

        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
            event=event,
            file_name=file_name,
            line_no=line_no,
            trace_call_end=True,
        )
        self._registrar.put_prompt_info(prompt_info)
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

    def prompt_start(
        self,
        trace_no: TraceNo,
        prompt_no: PromptNo,
        trace_args: Tuple[FrameType, str, Any],
        out: str,
    ) -> None:
        frame, event, _ = trace_args
        file_name = self._to_canonic(frame.f_code.co_filename)
        line_no = frame.f_lineno
        if module_name := frame.f_globals.get("__name__"):
            self._modules_to_trace.add(module_name)
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            open=True,
            event=event,
            file_name=file_name,
            line_no=line_no,
            stdout=out,
            started_at=datetime.datetime.now(),
        )
        self._prompt_info_map[(trace_no, prompt_no)] = prompt_info
        self._registrar.put_prompt_info(prompt_info)
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)
        self._last_prompt_frame_map[trace_no] = frame

    def prompt_end(
        self, trace_no: TraceNo, prompt_no: PromptNo, command: str
    ) -> None:
        prompt_info = self._prompt_info_map.pop((trace_no, prompt_no))
        prompt_info = dataclasses.replace(
            prompt_info,
            open=False,
            command=command,
            ended_at=datetime.datetime.now(),
        )
        self._registrar.put_prompt_info(prompt_info)
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

    def stdout(self, task_or_thread: Task | Thread, line: str):
        trace_no = self._trace_no_map[task_or_thread]
        stdout_info = StdoutInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            text=line,
            written_at=datetime.datetime.now(),
        )
        self._registrar.put_stdout_info(stdout_info)

    def close(self) -> None:
        self._thread_task_done_callback.close()

    def __enter__(self):
        self._peek_stdout = peek_stdout_by_task_and_thread(
            to_peek=self._tasks_and_threads, callback=self.stdout
        )
        self._entering_thread = threading.current_thread()
        self._peek_stdout.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._peek_stdout.__exit__(exc_type, exc_value, traceback)
        self.close()
        if self._entering_thread:
            if trace_no := self._trace_no_map.get(self._entering_thread):
                self.trace_end(trace_no)


class RegistrarProxy:
    def __init__(self, queue: QueueRegistry):
        self._queue = queue

    def put_trace_nos(self, trace_nos: Tuple[TraceNo, ...]) -> None:
        self._queue.put(("trace_nos", trace_nos, False))

    def put_trace_info(self, trace_info: TraceInfo) -> None:
        self._queue.put(("trace_info", trace_info, False))

    def put_prompt_info(self, prompt_info: PromptInfo) -> None:
        self._queue.put(("prompt_info", prompt_info, False))

    def put_prompt_info_for_trace(
        self, trace_no: TraceNo, prompt_info: PromptInfo
    ) -> None:
        key = f"prompt_info_{trace_no}"
        self._queue.put((key, prompt_info, False))

    def end_prompt_info_for_trace(self, trace_no: TraceNo) -> None:
        key = f"prompt_info_{trace_no}"
        self._queue.put((key, None, True))

    def put_stdout_info(self, stdout_info: StdoutInfo) -> None:
        self._queue.put(("stdout", stdout_info, False))


def ToCanonic() -> Callable[[str], str]:
    # Based on Bdb.canonic()
    # https://github.com/python/cpython/blob/v3.10.5/Lib/bdb.py#L39-L54

    cache: Dict[str, str] = {}

    def to_canonic(filename: str) -> str:
        if filename == "<" + filename[1:-1] + ">":
            return filename
        canonic = cache.get(filename)
        if not canonic:
            canonic = os.path.abspath(filename)
            canonic = os.path.normcase(canonic)
            cache[filename] = canonic
        return canonic

    return to_canonic
