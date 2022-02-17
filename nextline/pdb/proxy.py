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
    from ..utils.types import ThreadTaskId


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
        thread_asynctask_id: ThreadTaskId,
        modules_to_trace: Set[str],
        registry: Registry,
        ci_registry: PdbCIRegistry,
        prompting_counter: Callable[[], int],
    ):
        self.thread_task_id = thread_asynctask_id
        self.modules_to_trace = modules_to_trace
        self.registry = registry
        self.ci_registry = ci_registry
        self._prompting_counter = prompting_counter
        self.skip = MODULES_TO_SKIP

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
            self._open()

        class LocalTrace:
            def __init__(self, trace, callback):
                self._trace = trace
                self._callback = callback

            def __call__(self, frame, event, arg):
                if self._trace:
                    self._callback(frame, event, arg)
                    self._trace = self._trace(frame, event, arg)
                return self

        local_trace = LocalTrace(self._pdb_trace_dispatch, self._callback)
        return local_trace(frame, event, arg)

    def _open(self) -> None:

        self.q_stdin = queue.Queue()
        self.q_stdout = queue.Queue()

        self.pdb = CustomizedPdb(
            proxy=self,
            stdin=StreamIn(self.q_stdin),
            stdout=StreamOut(self.q_stdout),
            skip=self.skip,
            readrc=False,
        )
        self._pdb_trace_dispatch = self.pdb.trace_dispatch

        self.registry.open_register(self.thread_task_id)
        self.registry.register_list_item(
            "thread_task_ids", self.thread_task_id
        )

    def close(self):
        if self._first:
            return
        self.registry.close_register(self.thread_task_id)
        self.registry.deregister_list_item(
            "thread_task_ids", self.thread_task_id
        )

    def _callback(self, frame, event, arg):
        self._current_args = (frame, event, arg)

    def entering_cmdloop(self) -> None:
        """called by the customized pdb before it is entering the command loop"""

        frame, event, arg = self._current_args

        self._state = {
            "prompting": self._prompting_counter(),
            "file_name": self.pdb.canonic(frame.f_code.co_filename),
            "line_no": frame.f_lineno,
            "trace_event": event,
        }

        module_name = frame.f_globals.get("__name__")
        self.modules_to_trace.add(module_name)

        self.pdb_ci = PdbCommandInterface(
            self.pdb, self.q_stdin, self.q_stdout
        )
        self.pdb_ci.start()
        self.ci_registry.add(self.thread_task_id, self.pdb_ci)
        self.registry.register(self.thread_task_id, self._state.copy())

    def exited_cmdloop(self) -> None:
        """called by the customized pdb after it has exited from the command loop"""
        self._state["prompting"] = 0
        self.ci_registry.remove(self.thread_task_id)
        self.registry.register(self.thread_task_id, self._state.copy())
        self.pdb_ci.end()

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
