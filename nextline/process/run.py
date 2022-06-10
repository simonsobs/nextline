from __future__ import annotations

from multiprocessing import Queue
import concurrent.futures

from typing import Callable, Set, TypedDict, MutableMapping
from typing import Any, Tuple  # noqa F401
from typing_extensions import TypeAlias

from ..types import RunNo, TraceNo
from .trace import Trace
from .call import call_with_trace
from .callback import Callback, RegistrarProxy
from . import script

QueueDone: TypeAlias = "Queue[Tuple[Any, BaseException | None]]"

PdbCommand: TypeAlias = str
QueueCommands: TypeAlias = "Queue[Tuple[TraceNo, PdbCommand] | None]"
PdbCiMap: TypeAlias = MutableMapping[TraceNo, Callable[[PdbCommand], Any]]


class RunArg(TypedDict, total=False):
    run_no: RunNo
    statement: str
    filename: str
    queue: Queue[Tuple[str, Any, bool]]


class Context(TypedDict):
    callback: Callback
    pdb_ci_map: PdbCiMap
    modules_to_trace: Set[str]


def run(run_arg: RunArg, q_commands: QueueCommands, q_done: QueueDone):
    try:
        _run(run_arg, q_commands, q_done)
    except BaseException:
        q_done.put((None, None))
        raise


def _run(run_arg: RunArg, q_commands: QueueCommands, q_done: QueueDone):

    run_no = run_arg["run_no"]
    statement = run_arg.get("statement")
    filename = run_arg.get("script_file_name", "<string>")
    queue = run_arg["queue"]

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        q_done.put((None, e))
        return

    pdb_ci_map: PdbCiMap = {}
    modules_to_trace: Set[str] = set()

    with Callback(
        run_no=run_no,
        registrar=RegistrarProxy(queue),
        modules_to_trace=modules_to_trace,
    ) as callback:

        context = Context(
            callback=callback,
            pdb_ci_map=pdb_ci_map,
            modules_to_trace=modules_to_trace,
        )

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


def _command(q_commands: QueueCommands, pdb_ci_map: PdbCiMap):
    while m := q_commands.get():
        trace_id, command = m
        pdb_ci = pdb_ci_map[trace_id]
        pdb_ci(command)
