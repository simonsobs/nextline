from __future__ import annotations

import queue
import asyncio
import warnings
import fnmatch

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

from typing import Any, Set, Dict, Union, Callable, TYPE_CHECKING
from types import FrameType

if TYPE_CHECKING:
    from ..trace import Trace
    from ..types import TraceFunc
    from ..registry import PdbCIRegistry
    from ..utils import Registry, UniqThreadTaskIdComposer
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
    "nextline.queuedist",
    "nextlinegraphql.schema.bindables",
]


##__________________________________________________________________||
class PdbProxy:
    """A proxy of Pdb

    An instance of this class is created for each thread or async task.

    Parameters
    ----------
    id_composer : object
        A unique thread task ID composer
    trace : object
        A in stance of Trace
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
        id_composer: UniqThreadTaskIdComposer,
        trace: Trace,
        modules_to_trace: Set[str],
        registry: Registry,
        ci_registry: PdbCIRegistry,
        prompting_counter: Callable[[], int],
    ):
        self.id_composer = id_composer
        self.thread_asynctask_id = self.id_composer()
        self.trace = trace
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

        self._trace_func_all = self.trace_func_all
        self._traces = []

        self._first = True
        self._future = False

    def __call__(self, frame: FrameType, event: str, arg: Any) -> TraceFunc:
        """The main trace function

        This method will be called by the instance of Trace.
        The event should be always "call."
        """

        module_name = frame.f_globals.get("__name__")
        if self.pdb.is_skipped_module(module_name):
            return
        # print(module_name)

        if not event == "call":
            warnings.warn(
                f'The event is not "call": ({frame!r}, {event!r}, {arg!r})'
            )
        if self._first:
            return self.trace_func_register_new_thread_task(frame, event, arg)
        if self._future:
            return self.trace_func_reentry_after_future(frame, event, arg)
        return self.trace_func_all(frame, event, arg)

    def trace_func_register_new_thread_task(
        self, frame: FrameType, event: str, arg: Any
    ) -> TraceFunc:
        """The trace function for a new thread or async task

        The trace function of the first "call" event of the outermost
        scope of the thread or async task.

        """
        module_name = frame.f_globals.get("__name__")
        if not is_matched_to_any(module_name, self.modules_to_trace):
            return
        self._first = False
        self.registry.open_register(self.thread_asynctask_id)
        self.registry.register_list_item(
            "thread_task_ids", self.thread_asynctask_id
        )
        if self._trace_func_all:
            self._trace_func_all = self._trace_func_all(frame, event, arg)
        return self.trace_func_exit_thread_task

    def trace_func_reentry_after_future(
        self, frame: FrameType, event: str, arg: Any
    ) -> TraceFunc:
        """The trace function of reentry after "future" is returned"""
        module_name = frame.f_globals.get("__name__")
        if not is_matched_to_any(module_name, self.modules_to_trace):
            return
        self._future = False
        if self._trace_func_all:
            self._trace_func_all = self._trace_func_all(frame, event, arg)
        return self.trace_func_exit_thread_task

    def trace_func_exit_thread_task(
        self, frame: FrameType, event: str, arg: Any
    ) -> TraceFunc:
        """The trace function of the outermost scope in the thread or async task

        The trace function to detect the end of the thread or async
        task.

        """
        if self._trace_func_all:
            self._trace_func_all = self._trace_func_all(frame, event, arg)

        if event != "return":
            return self.trace_func_exit_thread_task

        if asyncio.isfuture(arg):
            # awaiting. will be called again
            self._future = True
            return

        self.registry.close_register(self.thread_asynctask_id)
        self.registry.deregister_list_item(
            "thread_task_ids", self.thread_asynctask_id
        )
        trace_id = self.id_composer()
        self.id_composer.exited(trace_id)
        # self.trace.returning()
        return

    def trace_func_all(
        self, frame: FrameType, event: str, arg: Any
    ) -> TraceFunc:
        """The trace function that calls the trace function of pdb"""

        module_name = frame.f_globals.get("__name__")
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        if self.pdb.is_skipped_module(module_name):
            # print(module_name)
            return

        func_name = frame.f_code.co_name
        # a function name
        # Note: '<module>' for the code produced by compile()
        if func_name == "<lambda>":
            return

        # print('{}.{}()'.format(module_name, func_name))
        # self.pdb.set_next(frame)

        trace = TraceBlock(
            thread_asynctask_id=self.thread_asynctask_id,
            pdb=self.pdb,
            registry=self.registry,
        )
        self._traces.append(trace)
        return trace(frame, event, arg)

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
class TraceBlock:
    def __init__(
        self,
        thread_asynctask_id: ThreadTaskId,
        pdb: CustomizedPdb,
        registry: Registry,
    ):
        self.pdb = pdb
        self.trace_func = pdb.trace_dispatch
        self.registry = registry
        self.thread_asynctask_id = thread_asynctask_id

    def __call__(self, frame: FrameType, event: str, arg: Any) -> TraceBlock:

        # if not frame.f_code.co_name == '<lambda>':
        #     file_name = self.pdb.canonic(frame.f_code.co_filename)
        #     line_no = frame.f_lineno
        #     self.registry.register_thread_task_state(self.thread_asynctask_id, file_name, line_no, event)

        if self.trace_func:
            self.trace_func = self.trace_func(frame, event, arg)
        return self


##__________________________________________________________________||
def is_matched_to_any(word: Union[str, None], patterns: Set[str]):
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
