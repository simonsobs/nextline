from __future__ import annotations

import sys
import queue  # noqa F401
from threading import Thread
import concurrent.futures

from typing import Callable, Dict, Any, TextIO, Tuple  # noqa F401
from typing_extensions import TypeAlias

from .trace import Trace
from .call import call_with_trace
from .types import TraceFunc
from .utils import SubscribableDict
from .pdb.ci import PdbCommandInterface

from . import script

QCommands: TypeAlias = "queue.Queue[Tuple[int, str] | None]"
QDone: TypeAlias = "queue.Queue[Tuple[Any, Any]]"


def run(registry: SubscribableDict, q_commands: QCommands, q_done: QDone):
    try:
        _run(registry, q_commands, q_done)
    except BaseException:
        q_done.put((None, None))
        raise


def _run(registry: SubscribableDict, q_commands: QCommands, q_done: QDone):

    code = _compile_code(registry, q_done)
    if code is None:
        return

    pdb_ci_map: Dict[int, PdbCommandInterface] = {}

    trace = Trace(registry=registry, pdb_ci_map=pdb_ci_map)

    def command():
        while m := q_commands.get():
            trace_id, command = m
            pdb_ci = pdb_ci_map[trace_id]
            pdb_ci.send_pdb_command(command)
            q_commands.task_done()
        q_commands.task_done()

    t_command = Thread(target=command, daemon=True)
    t_command.start()

    func = script.compose(code)
    wrap_stdout = registry["create_capture_stdout"]

    def call(
        func: Callable[[], Any],
        trace: TraceFunc,
        wrap_stdout: Callable[[TextIO], TextIO],
    ):
        result = None
        exception = None
        sys_stdout = sys.stdout
        try:
            sys.stdout = wrap_stdout(sys.stdout)
            try:
                result = call_with_trace(func, trace)
            except BaseException as e:
                exception = e
        finally:
            sys.stdout = sys_stdout
            return result, exception

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_call = executor.submit(call, func, trace, wrap_stdout)
        result, exception = future_to_call.result()

    q_commands.put(None)
    t_command.join()

    if callback := registry.get("callback"):
        try:
            callback.close()
        except BaseException:
            pass

    q_done.put((result, exception))


def _compile_code(registry: SubscribableDict, q_done: QDone):
    script_file_name = registry.get("script_file_name", "<string>")
    code = registry.get("statement")
    if isinstance(code, str):
        try:
            code = compile(code, script_file_name, "exec")
        except BaseException as exception:
            result = None
            q_done.put((result, exception))
            return None
    return code
