from __future__ import annotations

from queue import Queue  # noqa F401
import concurrent.futures

from typing import TypedDict
from typing import Any, Tuple, MutableMapping  # noqa F401
from typing_extensions import TypeAlias

from ..registrar import Registrar
from ..types import RunNo
from ..types import TraceNo  # noqa F401
from .trace import Trace
from .call import call_with_trace
from .pdb.ci import PdbCommandInterface  # noqa F401
from .callback import Callback
from . import script

QCommands: TypeAlias = "Queue[Tuple[TraceNo, str] | None]"
QDone: TypeAlias = "Queue[Tuple[Any, Any]]"
PdbCiMap: TypeAlias = "MutableMapping[TraceNo, PdbCommandInterface]"


class Context(TypedDict, total=False):
    run_no: RunNo
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

    run_no = context["run_no"]
    statement = context.get("statement")
    filename = context.get("script_file_name", "<string>")
    registrar = context["registrar"]

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        q_done.put((None, e))
        return

    pdb_ci_map: PdbCiMap = {}
    context["pdb_ci_map"] = pdb_ci_map

    with Callback(run_no=run_no, registrar=registrar) as callback:
        context["callback"] = callback

        trace = Trace(context=context)

        func = script.compose(code)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # TODO: Handle exceptions occurred in _command()
            future_to_command = executor.submit(
                _command, q_commands, pdb_ci_map
            )
            future_to_call = executor.submit(call_with_trace, func, trace)
            result, exception = future_to_call.result()
            q_commands.put(None)
            future_to_command.result()

    q_done.put((result, exception))


def _compile(code, filename):
    if isinstance(code, str):
        code = compile(code, filename, "exec")
    return code


def _command(q_commands: QCommands, pdb_ci_map: PdbCiMap):
    while m := q_commands.get():
        trace_id, command = m
        pdb_ci = pdb_ci_map[trace_id]
        pdb_ci.send_pdb_command(command)
        q_commands.task_done()
    q_commands.task_done()
