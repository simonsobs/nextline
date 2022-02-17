from __future__ import annotations

import queue
import fnmatch

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

from typing import Any, Set, Union, Callable, TYPE_CHECKING
from types import FrameType

if TYPE_CHECKING:
    from ..types import TraceFunc
    from ..registry import PdbCIRegistry
    from ..utils import Registry


MODULES_TO_SKIP = [
    "threading",
    "queue",
    "importlib",
    "asyncio.*",
    "janus",
    "codec",
    "concurrent.futures.*",
    "selectors",
    "weakref",
    "_weakrefset",
    "socket",
    "logging",
    "os",
    "collections.*",
    "importlib.*",
    "pathlib",
    "typing",
    "posixpath",
    "fnmatch",
    "_pytest.*",
    "pluggy.*",
    "nextline.pdb.*",
    "nextline.utils.*",
    "nextline.queuedist",
    "nextlinegraphql.schema.bindables",
]


class Registrar:
    """Register Pdb prompts to registries


    Parameters
    ----------
    trace_id : object
        The Id to distiugish each instance of Pdb
    modules_to_trace: set
        The set of modules to trace. This object is shared by multiple
        objects. Modules in which Pdb commands are prompted will be
        added.
    registry: object
        A registry
    ci_registry: object
        A registry
    prompting_counter : callable
        Used to count the Pdb command loops
    """

    def __init__(
        self,
        trace_id,
        registry: Registry,
        ci_registry: PdbCIRegistry,
        prompting_counter: Callable[[], int],
        modules_to_trace: Set[str],
    ):
        self._trace_id = trace_id
        self._registry = registry
        self._ci_registry = ci_registry
        self._prompting_counter = prompting_counter
        self.modules_to_trace = modules_to_trace
        self._skip = MODULES_TO_SKIP

    def open(self) -> TraceFunc:
        self._q_stdin = queue.Queue()
        self._q_stdout = queue.Queue()

        self._pdb = CustomizedPdb(
            registrar=self,
            stdin=StreamIn(self._q_stdin),
            stdout=StreamOut(self._q_stdout),
            skip=self._skip,
            readrc=False,
        )

        self._registry.open_register(self._trace_id)
        self._registry.register_list_item("thread_task_ids", self._trace_id)

        return self._pdb.trace_dispatch

    def close(self):
        self._registry.close_register(self._trace_id)
        self._registry.deregister_list_item("thread_task_ids", self._trace_id)

    def calling_trace(self, frame: FrameType, event: str, arg: Any) -> None:
        self._current_trace_args = (frame, event, arg)

    def exited_trace(self) -> None:
        self._current_trace_args = None

    def entering_cmdloop(self) -> None:
        frame, event, _ = self._current_trace_args

        module_name = frame.f_globals.get("__name__")
        self.modules_to_trace.add(module_name)

        self._state = {
            "prompting": self._prompting_counter(),
            "file_name": self._pdb.canonic(frame.f_code.co_filename),
            "line_no": frame.f_lineno,
            "trace_event": event,
        }

        self._pdb_ci = PdbCommandInterface(
            self._pdb, self._q_stdin, self._q_stdout
        )
        self._pdb_ci.start()
        self._ci_registry.add(self._trace_id, self._pdb_ci)
        self._registry.register(self._trace_id, self._state.copy())

    def exited_cmdloop(self) -> None:
        self._state["prompting"] = 0
        self._ci_registry.remove(self._trace_id)
        self._registry.register(self._trace_id, self._state.copy())
        self._pdb_ci.end()


class PdbProxy:
    """A proxy of Pdb

    An instance of this class is created for each thread or async task.

    Parameters
    ----------
    thread_asynctask_id : object
        A thread and async tack ID
    modules_to_trace: set
        The set of modules to trace. This object is shared by multiple
        instances of this class. Modules in which Pdb commands are
        prompted will be added.
    registry: object
    ci_registry: object
    prompting_counter : callable
    """

    def __init__(
        self,
        registrar: Registrar,
        modules_to_trace: Set[str],
    ):
        self.modules_to_trace = modules_to_trace
        self.skip = MODULES_TO_SKIP

        self._registrar = registrar

        self._first = True

    def __call__(self, frame: FrameType, event: str, arg: Any) -> TraceFunc:
        """The main trace function

        This method will be called by the instance of Trace.
        The event should be always "call."
        """

        if self._is_module_to_skip(frame):
            return

        if self._is_lambda(frame):
            return

        if not event == "call":
            raise RuntimeError(
                f'The event must be "call": ({frame!r}, {event!r}, {arg!r})'
            )

        if self._first:
            if not self._is_first_module_to_trace(frame):
                return
            self._first = False
            self._trace = self._registrar.open()

        class LocalTrace:
            def __init__(self, trace, callback):
                self._trace = trace
                self._callback = callback

            def __call__(self, frame, event, arg):
                if self._trace:
                    self._callback(frame, event, arg)
                    self._trace = self._trace(frame, event, arg)
                return self

        local_trace = LocalTrace(self._trace, self._callback)
        return local_trace(frame, event, arg)

    def close(self):
        if self._first:
            return
        self._registrar.close()

    def _callback(self, frame, event, arg):
        self._registrar.calling_trace(frame, event, arg)

    def _is_first_module_to_trace(self, frame) -> bool:
        module_name = frame.f_globals.get("__name__")
        return is_matched_to_any(module_name, self.modules_to_trace)

    def _is_module_to_skip(self, frame) -> bool:
        module_name = frame.f_globals.get("__name__")
        return is_matched_to_any(module_name, self.skip)

    def _is_lambda(self, frame) -> bool:
        func_name = frame.f_code.co_name
        return func_name == "<lambda>"


def is_matched_to_any(word: Union[str, None], patterns: Set[str]) -> bool:
    """
    based on Bdb.is_skipped_module()
    https://github.com/python/cpython/blob/v3.9.5/Lib/bdb.py#L191
    """
    if word is None:
        return False
    for pattern in patterns:
        if fnmatch.fnmatch(word, pattern):
            return True
    return False
