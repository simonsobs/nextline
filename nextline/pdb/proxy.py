from __future__ import annotations

import queue
import warnings
import fnmatch

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

from typing import Any, Set, Dict, Union, Callable, TYPE_CHECKING
from types import FrameType

if TYPE_CHECKING:
    from ..types import TraceFunc
    from ..registry import PdbCIRegistry
    from ..utils import Registry
    from ..utils.types import ThreadTaskId


##__________________________________________________________________||
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


##__________________________________________________________________||
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
        self.thread_asynctask_id = thread_asynctask_id
        self.modules_to_trace = modules_to_trace
        self.registry = registry
        self.ci_registry = ci_registry
        self.skip = MODULES_TO_SKIP

        self.q_stdin = queue.Queue()
        self.q_stdout = queue.Queue()

        self.pdb = CustomizedPdb(
            proxy=self,
            prompting_counter=prompting_counter,
            stdin=StreamIn(self.q_stdin),
            stdout=StreamOut(self.q_stdout),
            skip=self.skip,
            readrc=False,
        )

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
            warnings.warn(
                f'The event is not "call": ({frame!r}, {event!r}, {arg!r})'
            )

        if self._first:
            if not self._is_first_module_to_trace(frame):
                return
            self._first = False
            self._call_once()

        return self.pdb.trace_dispatch(frame, event, arg)

    def _is_first_module_to_trace(self, frame) -> bool:
        module_name = frame.f_globals.get("__name__")
        return is_matched_to_any(module_name, self.modules_to_trace)

    def _is_module_to_skip(self, frame) -> bool:
        module_name = frame.f_globals.get("__name__")
        return is_matched_to_any(module_name, self.skip)

    def _is_lambda(self, frame) -> bool:
        func_name = frame.f_code.co_name
        return func_name == "<lambda>"

    def _call_once(self) -> None:

        self.registry.open_register(self.thread_asynctask_id)
        self.registry.register_list_item(
            "thread_task_ids", self.thread_asynctask_id
        )

    def close(self):
        if self._first:
            return
        self.registry.close_register(self.thread_asynctask_id)
        self.registry.deregister_list_item(
            "thread_task_ids", self.thread_asynctask_id
        )

    def entering_cmdloop(self, frame: FrameType, state: Dict) -> None:
        """called by the customized pdb before it is entering the command loop"""
        module_name = frame.f_globals.get("__name__")
        self.modules_to_trace.add(module_name)

        self.pdb_ci = PdbCommandInterface(
            self.pdb, self.q_stdin, self.q_stdout
        )
        self.pdb_ci.start()
        self.ci_registry.add(self.thread_asynctask_id, self.pdb_ci)
        self.registry.register(self.thread_asynctask_id, state.copy())

    def exited_cmdloop(self, state: Dict) -> None:
        """called by the customized pdb after it has exited from the command loop"""
        self.ci_registry.remove(self.thread_asynctask_id)
        self.registry.register(self.thread_asynctask_id, state.copy())
        self.pdb_ci.end()


##__________________________________________________________________||
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


##__________________________________________________________________||
