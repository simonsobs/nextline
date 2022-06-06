from __future__ import annotations

import sys
from asyncio import Task
from threading import Thread
from queue import Queue  # noqa F401
import concurrent.futures
from weakref import WeakKeyDictionary
import datetime

from typing import Callable, Any, TextIO, TypedDict
from typing import Tuple, MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from .registrar import Registrar
from .trace import Trace
from .call import call_with_trace
from .types import TraceFunc, PromptInfo
from .pdb.ci import PdbCommandInterface  # noqa F401
from .utils import ThreadTaskDoneCallback

from . import script

QCommands: TypeAlias = "Queue[Tuple[int, str] | None]"
QDone: TypeAlias = "Queue[Tuple[Any, Any]]"
PdbCiMap: TypeAlias = "MutableMapping[int, PdbCommandInterface]"
TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"


class Callback:
    def __init__(self, context: Context):
        self._context = context
        self._run_no = context["run_no"]
        self._registrar = self._context["registrar"]
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self.task_or_thread_end
        )

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self.trace_end(trace_no)

    def trace_start(self, trace_no: int):
        self._registrar.trace_start(trace_no)
        task_or_thread = self._thread_task_done_callback.register()
        self._trace_no_map[task_or_thread] = trace_no

    def trace_end(self, trace_no: int):
        self._registrar.trace_end(trace_no)

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
        self._registrar.prompt_start(prompt_info)

    def prompt_end(
        self, trace_no, prompt_no, event, file_name, line_no, command
    ) -> None:
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=prompt_no,
            open=False,
            event=event,
            file_name=file_name,
            line_no=line_no,
            command=command,
            ended_at=datetime.datetime.now(),
        )
        self._registrar.prompt_end(prompt_info)

    def close(self) -> None:
        self._thread_task_done_callback.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        self.close()


class Context(TypedDict, total=False):
    run_no: int
    statement: str
    filename: str
    create_capture_stdout: Callable[[TextIO], TextIO]
    registrar: Registrar
    callback: Callback
    pdb_ci_map: PdbCiMap


def run(context: Context, q_commands: QCommands, q_done: QDone):
    try:
        _run(context, q_commands, q_done)
    except BaseException:
        q_done.put((None, None))
        raise


def _run(context: Context, q_commands: QCommands, q_done: QDone):

    statement = context.get("statement")
    filename = context.get("script_file_name", "<string>")
    wrap_stdout = context["create_capture_stdout"]

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        q_done.put((None, e))
        return

    pdb_ci_map: PdbCiMap = {}
    context["pdb_ci_map"] = pdb_ci_map

    with Callback(context) as callback:
        context["callback"] = callback

        trace = Trace(context=context)

        func = script.compose(code)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # TODO: Handle exceptions occurred in _command()
            future_to_command = executor.submit(
                _command, q_commands, pdb_ci_map
            )
            future_to_call = executor.submit(_exec, func, trace, wrap_stdout)
            result, exception = future_to_call.result()
            q_commands.put(None)
            future_to_command.result()

    q_done.put((result, exception))


def _compile(code, filename):
    if isinstance(code, str):
        code = compile(code, filename, "exec")
    return code


def _exec(
    func: Callable[[], Any],
    trace: TraceFunc,
    wrap_stdout: Callable[[TextIO], TextIO],
):
    ret = None
    exc = None
    sys_stdout = sys.stdout
    try:
        sys.stdout = wrap_stdout(sys.stdout)
        ret, exc = call_with_trace(func, trace)
    finally:
        sys.stdout = sys_stdout
        return ret, exc


def _command(q_commands: QCommands, pdb_ci_map: PdbCiMap):
    while m := q_commands.get():
        trace_id, command = m
        pdb_ci = pdb_ci_map[trace_id]
        pdb_ci.send_pdb_command(command)
        q_commands.task_done()
    q_commands.task_done()
