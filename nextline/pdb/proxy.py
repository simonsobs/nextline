from __future__ import annotations

import queue

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

from typing import Any, Optional, Set, Callable, TYPE_CHECKING
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
        self._opened = False

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

        self._opened = True

        return self._pdb.trace_dispatch

    def close(self):
        if not self._opened:
            return
        self._registry.close_register(self._trace_id)
        self._registry.deregister_list_item("thread_task_ids", self._trace_id)

    def calling_trace(self, frame: FrameType, event: str, arg: Any) -> None:
        self._current_trace_args = (frame, event, arg)

    def exited_trace(self) -> None:
        self._current_trace_args = None

    def entering_cmdloop(self) -> None:
        if not self._current_trace_args:
            raise RuntimeError("calling_trace() must be called first")

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

    def __init__(self, registrar: Registrar):
        self._registrar = registrar
        self._first = True

    def __call__(self, frame, event, arg) -> Optional[TraceFunc]:

        if self._first:
            self._first = False
            self._trace = self._registrar.open()

        def create_local_trace():
            trace = self._trace

            def local_trace(frame, event, arg):
                nonlocal trace
                self._registrar.calling_trace(frame, event, arg)
                trace = trace(frame, event, arg)
                self._registrar.exited_trace()
                if trace:
                    return local_trace

            return local_trace

        return create_local_trace()(frame, event, arg)
