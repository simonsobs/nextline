from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from logging import getLogger
from typing import Any, Callable, Set, Tuple, TypedDict, TypeVar

from . import script
from .call import call_with_trace
from .callback import Callback, RegistrarProxy
from .trace import Trace
from .types import PdbCiMap, QueueCommands, QueueRegistry, RunArg

_T = TypeVar("_T")


class Context(TypedDict):
    callback: Callback
    pdb_ci_map: PdbCiMap
    modules_to_trace: Set[str]


def run_(
    run_arg: RunArg,
    q_commands: QueueCommands,
    q_registry: QueueRegistry,
) -> Tuple[Any, BaseException | None]:

    run_no = run_arg["run_no"]
    statement = run_arg.get("statement")
    filename = run_arg.get("script_file_name", "<string>")

    try:
        code = _compile(statement, filename)
    except BaseException as e:
        return None, e

    pdb_ci_map: PdbCiMap = {}
    modules_to_trace: Set[str] = set()

    with Callback(
        run_no=run_no,
        registrar=RegistrarProxy(q_registry),
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

    return result, exception


def _compile(code, filename):
    if isinstance(code, str):
        code = compile(code, filename, "exec")
    return code


@contextmanager
def relay_commands(q_commands: QueueCommands, pdb_ci_map: PdbCiMap):
    def fn() -> None:
        assert q_commands
        while m := q_commands.get():
            command, prompt_no, trace_no = m
            pdb_ci = pdb_ci_map[trace_no]
            pdb_ci(command, prompt_no)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(try_again_on_error, fn)  # type: ignore
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
