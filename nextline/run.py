from __future__ import annotations

from threading import Thread
import queue
import janus
from typing import TYPE_CHECKING, Dict, Tuple, Any

from .trace import Trace
from .utils import SubscribableDict
from .call import call_with_trace
from . import script

if TYPE_CHECKING:
    from .pdb.ci import PdbCommandInterface


def run(
    registry: SubscribableDict,
    q_commands: queue.Queue[Tuple[int, str] | None],
    q_done: queue.Queue[janus.Queue[Tuple[Any, Any]]],
):

    statement = registry.get("statement")
    script_file_name = registry.get("script_file_name", "<string>")

    pdb_ci_map: Dict[int, PdbCommandInterface] = {}

    def done(result, exception):
        janus_q = q_done.get()
        janus_q.sync_q.put((result, exception))

    trace = Trace(
        registry=registry,
        pdb_ci_map=pdb_ci_map,
    )

    code = statement
    if isinstance(code, str):
        try:
            code = compile(code, script_file_name, "exec")
        except BaseException as e:
            done(None, e)
            return

    def command():
        while m := q_commands.get():
            trace_id, command = m
            pdb_ci = pdb_ci_map[trace_id]
            pdb_ci.send_pdb_command(command)
            q_commands.task_done()

    t_command = Thread(target=command, daemon=True)
    t_command.start()

    func = script.compose(code)
    result = None
    exception = None

    def call():
        nonlocal result, exception
        try:
            result = call_with_trace(func, trace)
        except BaseException as e:
            exception = e

    t_call = Thread(target=call, daemon=True)
    t_call.start()
    t_call.join()
    q_commands.put(None)
    t_command.join()

    if callback := registry.get("callback"):
        try:
            callback.close()
        except BaseException:
            pass

    done(result, exception)
