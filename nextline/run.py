from __future__ import annotations

from asyncio import Task
from threading import Thread
from queue import Queue  # noqa F401
import concurrent.futures
from weakref import WeakKeyDictionary
import datetime
import dataclasses

from typing import Callable, Any, Set, TypedDict
from typing import Tuple, MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from .registrar import Registrar
from .trace import Trace
from .call import call_with_trace
from .types import TraceFunc, TraceInfo, PromptInfo, StdoutInfo
from .pdb.ci import PdbCommandInterface  # noqa F401
from .utils import ThreadTaskDoneCallback, ThreadTaskIdComposer
from .io import peek_stdout_by_task_and_thread

from . import script

QCommands: TypeAlias = "Queue[Tuple[int, str] | None]"
QDone: TypeAlias = "Queue[Tuple[Any, Any]]"
PdbCiMap: TypeAlias = "MutableMapping[int, PdbCommandInterface]"
TraceNoMap: TypeAlias = "MutableMapping[Task | Thread, int]"
TraceInfoMap: TypeAlias = "MutableMapping[int, TraceInfo]"


class Callback:
    def __init__(self, run_no: int, registrar: Registrar):
        self._run_no = run_no
        self._registrar = registrar
        self._trace_nos: Tuple[int, ...] = ()
        self._trace_no_map: TraceNoMap = WeakKeyDictionary()
        self._trace_id_factory = ThreadTaskIdComposer()
        self._trace_info_map: TraceInfoMap = {}
        self._thread_task_done_callback = ThreadTaskDoneCallback(
            done=self.task_or_thread_end
        )
        self._tasks_and_threads: Set[Task | Thread] = set()

    def task_or_thread_end(self, task_or_thread: Task | Thread):
        trace_no = self._trace_no_map[task_or_thread]
        self.trace_end(trace_no)

    def trace_start(self, trace_no: int):

        # TODO: Putting a prompt info for now because otherwise tests get stuck
        # sometimes for an unknown reason. Need to investigate
        prompt_info = PromptInfo(
            run_no=self._run_no,
            trace_no=trace_no,
            prompt_no=-1,
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

    def trace_end(self, trace_no: int):
        self._registrar.end_prompt_info_for_trace(trace_no)

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
        self._registrar.put_prompt_info(prompt_info)
        self._registrar.put_prompt_info_for_trace(trace_no, prompt_info)

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


class Context(TypedDict, total=False):
    run_no: int
    statement: str
    filename: str
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

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        q_done.put((None, e))
        return

    pdb_ci_map: PdbCiMap = {}
    context["pdb_ci_map"] = pdb_ci_map

    with Callback(
        run_no=context["run_no"], registrar=context["registrar"]
    ) as callback:
        context["callback"] = callback

        trace = Trace(context=context)

        func = script.compose(code)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # TODO: Handle exceptions occurred in _command()
            future_to_command = executor.submit(
                _command, q_commands, pdb_ci_map
            )
            future_to_call = executor.submit(_exec, func, trace)
            result, exception = future_to_call.result()
            q_commands.put(None)
            future_to_command.result()

    q_done.put((result, exception))


def _compile(code, filename):
    if isinstance(code, str):
        code = compile(code, filename, "exec")
    return code


def _exec(func: Callable[[], Any], trace: TraceFunc):
    ret, exc = call_with_trace(func, trace)
    return ret, exc


def _command(q_commands: QCommands, pdb_ci_map: PdbCiMap):
    while m := q_commands.get():
        trace_id, command = m
        pdb_ci = pdb_ci_map[trace_id]
        pdb_ci.send_pdb_command(command)
        q_commands.task_done()
    q_commands.task_done()
