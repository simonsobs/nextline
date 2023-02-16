from __future__ import annotations

from contextlib import _GeneratorContextManager
import dataclasses
import datetime
import os
import threading
from asyncio import Task
from contextlib import contextmanager
from threading import Thread
from types import FrameType
from typing import (  # noqa F401
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    MutableMapping,
    Optional,
    Set,
    Tuple,
)
from weakref import WeakKeyDictionary

from typing_extensions import TypeAlias

from nextline.types import (
    PromptInfo,
    PromptNo,
    RunNo,
    StdoutInfo,
    TaskNo,
    ThreadNo,
    TraceInfo,
    TraceNo,
)
from nextline.utils import (
    ThreadTaskDoneCallback,
    ThreadTaskIdComposer,
    current_task_or_thread,
)

from .io import peek_stdout_by_task_and_thread

if TYPE_CHECKING:
    from .run import QueueRegistry

TraceArgs: TypeAlias = Tuple[FrameType, str, Any]

TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, TraceNo]"
TraceInfoMap: TypeAlias = "Dict[TraceNo, TraceInfo]"
PromptInfoMap: TypeAlias = "Dict[Tuple[TraceNo, PromptNo], PromptInfo]"


class TraceNumbersRegistrar:
    def __init__(self, registrar: RegistrarProxy):
        self._registrar = registrar
        self._trace_nos: Tuple[TraceNo, ...] = ()
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()

    def trace_start(self, trace_no: TraceNo):
        self._trace_nos = self._trace_nos + (trace_no,)
        self._registrar.put_trace_nos(self._trace_nos)

    def trace_end(self, trace_no: TraceNo):
        nosl = list(self._trace_nos)
        nosl.remove(trace_no)
        self._trace_nos = tuple(nosl)
        self._registrar.put_trace_nos(self._trace_nos)


class TraceInfoRegistrar:
    def __init__(self, run_no: RunNo, registrar: RegistrarProxy):
        self._run_no = run_no
        self._registrar = registrar
        self._trace_context_map: Dict[TraceNo, _GeneratorContextManager] = {}

    def trace_start(
        self,
        trace_no: TraceNo,
        thread_no: ThreadNo,
        task_no: Optional[TaskNo],
    ) -> None:
        @contextmanager
        def _trace():

            trace_info = TraceInfo(
                run_no=self._run_no,
                trace_no=trace_no,
                thread_no=thread_no,
                task_no=task_no,
                state="running",
                started_at=datetime.datetime.utcnow(),
            )
            self._registrar.put_trace_info(trace_info)

            yield

            trace_info_end = dataclasses.replace(
                trace_info,
                state='finished',
                ended_at=datetime.datetime.utcnow(),
            )
            self._registrar.put_trace_info(trace_info_end)

        context = _trace()
        context.__enter__()
        self._trace_context_map[trace_no] = context

    def trace_end(self, trace_no: TraceNo) -> None:
        context = self._trace_context_map.pop(trace_no)
        context.__exit__(None, None, None)


class PromptInfoRegistrar:
    def __init__(self, run_no: RunNo, registrar: RegistrarProxy):
        self._run_no = run_no
        self._registrar = registrar
        self._trace_context_map: Dict[TraceNo, _GeneratorContextManager] = {}
        self._prompt_context_map: Dict[PromptNo, _GeneratorContextManager] = {}
        self._last_prompt_frame_map: Dict[TraceNo, FrameType] = {}

    def trace_start(self, trace_no: TraceNo) -> None:
        @contextmanager
        def _trace():

            # TODO: Putting a prompt info for now because otherwise tests get stuck
            # sometimes for an unknown reason. Need to investigate
            prompt_info = PromptInfo(
                run_no=self._run_no,
                trace_no=trace_no,
                prompt_no=PromptNo(-1),
                open=False,
            )
            self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

            yield

            self._registrar.end_prompt_info_for_trace(trace_no)

        context = _trace()
        context.__enter__()
        self._trace_context_map[trace_no] = context

    def trace_end(self, trace_no: TraceNo) -> None:
        context = self._trace_context_map.pop(trace_no)
        context.__exit__(None, None, None)

    @contextmanager
    def trace_call(self, trace_no: TraceNo, trace_args: TraceArgs):

        try:
            yield
        finally:
            # return
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

    def prompt_start(
        self,
        trace_no: TraceNo,
        prompt_no: PromptNo,
        trace_args: TraceArgs,
        out: str,
    ) -> None:
        @contextmanager
        def _prompt() -> Generator[None, str, None]:

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

        context = _prompt()
        context.__enter__()
        self._prompt_context_map[prompt_no] = context

    def prompt_end(self, trace_no: TraceNo, prompt_no: PromptNo, command: str) -> None:
        context = self._prompt_context_map.pop(prompt_no)
        context.gen.send(command)
        context.__exit__(None, None, None)


class AddModuleToTrace:
    '''Let Python modules be traced in new threads and asyncio tasks.'''

    def __init__(self, modules_to_trace: Set[str]):
        self._modules_to_trace = modules_to_trace

    def prompt_start(self, trace_arg: TraceArgs):
        frame, _, _ = trace_arg
        if module_name := frame.f_globals.get('__name__'):
            self._modules_to_trace.add(module_name)


class StdoutRegistrar:
    def __init__(self, run_no: RunNo, registrar: RegistrarProxy):
        self._run_no = run_no
        self._registrar = registrar

    def stdout_write(self, trace_no: TraceNo, line: str):
        stdout_info = StdoutInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            text=line,
            written_at=datetime.datetime.utcnow(),
        )
        self._registrar.put_stdout_info(stdout_info)


class Callback:
    def __init__(
        self,
        run_no: RunNo,
        registrar: RegistrarProxy,
        modules_to_trace: Set[str],
    ):
        self._add_module_to_trace = AddModuleToTrace(modules_to_trace)
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._trace_id_factory = ThreadTaskIdComposer()
        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self.task_or_thread_end
        )
        self._tasks_and_threads: Set[Task | Thread] = set()
        self._entering_thread: Optional[Thread] = None
        self._trace_numbers_registrar = TraceNumbersRegistrar(registrar=registrar)
        self._trace_info_registrar = TraceInfoRegistrar(
            run_no=run_no, registrar=registrar
        )
        self._prompt_info_registrar = PromptInfoRegistrar(
            run_no=run_no, registrar=registrar
        )
        self._stdout_registrar = StdoutRegistrar(run_no=run_no, registrar=registrar)

    def task_or_thread_start(self, trace_no: TraceNo) -> None:
        task_or_thread = current_task_or_thread()
        self._trace_no_map[task_or_thread] = trace_no

        if task_or_thread is not self._entering_thread:
            self._thread_task_done_callback.register(task_or_thread)

        self._tasks_and_threads.add(task_or_thread)

        self.trace_start(trace_no)

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self.trace_end(trace_no)

    def trace_start(self, trace_no: TraceNo):
        self._trace_numbers_registrar.trace_start(trace_no=trace_no)

        thread_task_id = self._trace_id_factory()
        thread_no = thread_task_id.thread_no
        task_no = thread_task_id.task_no

        self._prompt_info_registrar.trace_start(trace_no=trace_no)

        self._trace_info_registrar.trace_start(
            trace_no=trace_no,
            thread_no=thread_no,
            task_no=task_no,
        )

    def trace_end(self, trace_no: TraceNo):
        self._trace_numbers_registrar.trace_end(trace_no=trace_no)
        self._prompt_info_registrar.trace_end(trace_no=trace_no)
        self._trace_info_registrar.trace_end(trace_no=trace_no)

    @contextmanager
    def trace_call(self, trace_no: TraceNo, trace_args: TraceArgs):

        with self._prompt_info_registrar.trace_call(
            trace_no=trace_no, trace_args=trace_args
        ):
            yield

    def prompt_start(
        self,
        trace_no: TraceNo,
        prompt_no: PromptNo,
        trace_args: TraceArgs,
        out: str,
    ) -> None:

        self._prompt_info_registrar.prompt_start(
            trace_no=trace_no,
            prompt_no=prompt_no,
            trace_args=trace_args,
            out=out,
        )

        self._add_module_to_trace.prompt_start(trace_args)

    def prompt_end(self, trace_no: TraceNo, prompt_no: PromptNo, command: str) -> None:
        self._prompt_info_registrar.prompt_end(
            trace_no=trace_no,
            prompt_no=prompt_no,
            command=command,
        )

    def stdout(self, task_or_thread: Task | Thread, line: str):
        trace_no = self._trace_no_map[task_or_thread]
        self._stdout_registrar.stdout_write(trace_no=trace_no, line=line)

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


_to_canonic = ToCanonic()
