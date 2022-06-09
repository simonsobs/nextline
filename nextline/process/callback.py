from __future__ import annotations

import os
from asyncio import Task
from threading import Thread
from weakref import WeakKeyDictionary
import datetime
import dataclasses

from typing import TYPE_CHECKING, Callable, Tuple, Set
from typing import Dict, MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from ..registrar import Registrar
from ..types import RunNo, TraceNo, PromptNo, TraceInfo, PromptInfo, StdoutInfo
from ..utils import ThreadTaskDoneCallback, ThreadTaskIdComposer
from .io import peek_stdout_by_task_and_thread

if TYPE_CHECKING:
    from .pdb.proxy import PdbInterface

TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, TraceNo]"
TraceInfoMap: TypeAlias = "Dict[TraceNo, TraceInfo]"
PromptInfoMap: TypeAlias = "Dict[Tuple[TraceNo, PromptNo], PromptInfo]"
PdbIMap: TypeAlias = "Dict[TraceNo, PdbInterface]"


class Callback:
    def __init__(self, run_no: RunNo, registrar: Registrar):
        self._run_no = run_no
        self._registrar = registrar
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

        task_or_thread = self._thread_task_done_callback.register()
        self._trace_no_map[task_or_thread] = trace_no
        self._tasks_and_threads.add(task_or_thread)

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

    def prompt_start(
        self, trace_no, prompt_no, event, file_name, line_no, out
    ) -> None:
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

    def prompt_end(
        self, trace_no: TraceNo, prompt_no: PromptNo, command
    ) -> None:
        prompt_info = self._prompt_info_map.pop((trace_no, prompt_no))
        prompt_info = dataclasses.replace(
            prompt_info,
            open=False,
            stdout=None,
            command=command,
            started_at=None,
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
        self._peek_stdout.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._peek_stdout.__exit__(exc_type, exc_value, traceback)
        self.close()


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
