from __future__ import annotations

import sys
from queue import Queue  # noqa F401
import concurrent.futures

from typing import Callable, Dict, Any, TextIO, TypedDict
from typing import Tuple  # noqa F401
from typing_extensions import TypeAlias

from .trace import Trace
from .call import call_with_trace
from .types import TraceFunc
from .utils import SubscribableDict
from .pdb.ci import PdbCommandInterface

from . import script

QCommands: TypeAlias = "Queue[Tuple[int, str] | None]"
QDone: TypeAlias = "Queue[Tuple[Any, Any]]"


class Context(TypedDict, total=False):
    statement: str
    filename: str
    create_capture_stdout: Callable[[TextIO], TextIO]
    run_no_count: Callable[[], int]
    registry: SubscribableDict


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

    registry = context["registry"]

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        q_done.put((None, e))
        return

    pdb_ci_map: Dict[int, PdbCommandInterface] = {}

    trace = Trace(registry=registry, pdb_ci_map=pdb_ci_map)

    func = script.compose(code)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # TODO: Handle exceptions occurred in _command()
        future_to_command = executor.submit(_command, q_commands, pdb_ci_map)
        future_to_call = executor.submit(_exec, func, trace, wrap_stdout)
        result, exception = future_to_call.result()
        q_commands.put(None)
        future_to_command.result()

    if callback := registry.get("callback"):
        try:
            callback.close()
        except BaseException:
            pass

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


def _command(
    q_commands: QCommands, pdb_ci_map: Dict[int, PdbCommandInterface]
):
    while m := q_commands.get():
        trace_id, command = m
        pdb_ci = pdb_ci_map[trace_id]
        pdb_ci.send_pdb_command(command)
        q_commands.task_done()
    q_commands.task_done()
