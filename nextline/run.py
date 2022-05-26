from __future__ import annotations

import sys
from threading import Thread
from typing import TYPE_CHECKING, Dict
from typing_extensions import TypeAlias

from .trace import Trace
from .call import call_with_trace
from .utils import ExcThread
from . import script

if TYPE_CHECKING:
    import queue  # noqa F401
    from typing import Any, Tuple  # noqa F401
    from .utils import SubscribableDict
    from .pdb.ci import PdbCommandInterface

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
    result = None
    exception = None

    def call():
        nonlocal result, exception
        sys_stdout = sys.stdout
        create_capture_stdout = registry["create_capture_stdout"]
        try:
            sys.stdout = create_capture_stdout(sys.stdout)
            try:
                result = call_with_trace(func, trace)
            except BaseException as e:
                exception = e
        finally:
            sys.stdout = sys_stdout

    t_call = ExcThread(target=call, daemon=True)
    t_call.start()
    t_call.join()
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
