from __future__ import annotations

import dataclasses
import datetime
import os
from types import FrameType
from typing import Callable, Dict, Generator, Tuple

from apluggy import PluginManager, contextmanager

from nextline.process.trace.spec import hookimpl
from nextline.process.trace.types import TraceArgs
from nextline.process.types import QueueRegistry
from nextline.types import PromptInfo, PromptNo, RunNo, StdoutInfo, TraceInfo, TraceNo


class TraceNumbersRegistrar:
    @hookimpl
    def init(self, registrar: RegistrarProxy):
        self._registrar = registrar
        self._trace_nos: Tuple[TraceNo, ...] = ()

    @hookimpl
    def trace_start(self, trace_no: TraceNo):
        self._trace_nos = self._trace_nos + (trace_no,)
        self._registrar.put_trace_nos(self._trace_nos)

    @hookimpl
    def trace_end(self, trace_no: TraceNo):
        nosl = list(self._trace_nos)
        nosl.remove(trace_no)
        self._trace_nos = tuple(nosl)
        self._registrar.put_trace_nos(self._trace_nos)


class TraceInfoRegistrar:
    @hookimpl
    def init(self, hook: PluginManager, run_no: RunNo, registrar: RegistrarProxy):
        self._hook = hook
        self._run_no = run_no
        self._registrar = registrar
        self._trace_info_map: Dict[TraceNo, TraceInfo] = {}

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:
        assert trace_no == self._hook.hook.current_trace_no()
        thread_no = self._hook.hook.current_thread_no()
        task_no = self._hook.hook.current_task_no()

        trace_info = TraceInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            thread_no=thread_no,
            task_no=task_no,
            state="running",
            started_at=datetime.datetime.utcnow(),
        )
        self._trace_info_map[trace_no] = trace_info
        self._registrar.put_trace_info(trace_info)

    @hookimpl
    def trace_end(self, trace_no: TraceNo) -> None:
        trace_info = self._trace_info_map.pop(trace_no)
        trace_info_end = dataclasses.replace(
            trace_info,
            state='finished',
            ended_at=datetime.datetime.utcnow(),
        )
        self._registrar.put_trace_info(trace_info_end)


class PromptInfoRegistrar:
    def __init__(self) -> None:
        self._last_prompt_frame_map: Dict[TraceNo, FrameType] = {}

    @hookimpl
    def init(self, run_no: RunNo, registrar: RegistrarProxy):
        self._run_no = run_no
        self._registrar = registrar

    @hookimpl
    def trace_start(self, trace_no: TraceNo) -> None:

        # TODO: Putting a prompt info for now because otherwise tests get stuck
        # sometimes for an unknown reason. Need to investigate
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=PromptNo(-1),
            open=False,
        )
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

    @hookimpl
    def trace_end(self, trace_no: TraceNo) -> None:
        self._registrar.end_prompt_info_for_trace(trace_no)

    @hookimpl
    @contextmanager
    def trace_call(self, trace_no: TraceNo, trace_args: TraceArgs):

        try:
            yield
        finally:
            frame, event, _ = trace_args
            file_name = _to_canonic(frame.f_code.co_filename)
            line_no = frame.f_lineno

            if frame is not self._last_prompt_frame_map.get(trace_no):
                return

            # TODO: Sending a prompt info with "open=False" for now so that the
            #       arrow in the web UI moves when the Pdb is "continuing."

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

    @hookimpl
    @contextmanager
    def prompt(
        self,
        trace_no: TraceNo,
        prompt_no: PromptNo,
        trace_args: TraceArgs,
        out: str,
    ) -> Generator[None, str, None]:

        frame, event, _ = trace_args
        file_name = _to_canonic(frame.f_code.co_filename)
        line_no = frame.f_lineno
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            open=True,
            event=event,
            file_name=file_name,
            line_no=line_no,
            stdout=out,
            started_at=datetime.datetime.utcnow(),
        )
        self._registrar.put_prompt_info(prompt_info)
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

        self._last_prompt_frame_map[trace_no] = frame

        # Yield twice: once to receive from send(), and once to exit.
        # https://stackoverflow.com/a/68304565/7309855
        command = yield
        yield

        prompt_info_end = dataclasses.replace(
            prompt_info,
            open=False,
            command=command,
            ended_at=datetime.datetime.utcnow(),
        )
        self._registrar.put_prompt_info(prompt_info_end)
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info_end)


class StdoutRegistrar:
    @hookimpl
    def init(self, run_no: RunNo, registrar: RegistrarProxy):
        self._run_no = run_no
        self._registrar = registrar

    @hookimpl
    def stdout(self, trace_no: TraceNo, line: str):
        stdout_info = StdoutInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            text=line,
            written_at=datetime.datetime.utcnow(),
        )
        self._registrar.put_stdout_info(stdout_info)


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


_to_canonic = ToCanonic()
