from __future__ import annotations

from multiprocessing import Queue
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from logging import getLogger

from typing import Callable, Set, TypeVar, TypedDict, MutableMapping
from typing import Any, Tuple  # noqa F401
from typing_extensions import TypeAlias

from ..types import RunNo, TraceNo
from .trace import Trace
from .call import call_with_trace
from .callback import Callback, RegistrarProxy
from . import script

_T = TypeVar("_T")

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

        with relay_commands(q_commands, pdb_ci_map):
            result, exception = call_with_trace(func, trace)

    q_done.put((result, exception))


def _compile(code, filename):
    if isinstance(code, str):
        code = compile(code, filename, "exec")
    return code


@contextmanager
def relay_commands(q_commands: QueueCommands, pdb_ci_map: PdbCiMap):
    def fn():
        while m := q_commands.get():
            trace_id, command = m
            pdb_ci = pdb_ci_map[trace_id]
            pdb_ci(command)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(try_again_on_error, fn)
        try:
            yield
        finally:
            q_commands.put(None)
            future.result()


def try_again_on_error(func: Callable[[], _T]) -> _T:
    while True:
        try:
            return func()
        # except KeyboardInterrupt:
        #     raise
        except BaseException:
            logger = getLogger(__name__)
            logger.exception("")
