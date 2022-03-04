from __future__ import annotations

import queue
from itertools import count
from weakref import WeakKeyDictionary

from ..utils import UniqThreadTaskIdComposer, ThreadTaskDoneCallback
from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut


from typing import Any, Optional, Set, Callable, TYPE_CHECKING, Tuple
from types import FrameType

if TYPE_CHECKING:
    from ..types import TraceFunc
    from ..registry import PdbCIRegistry
    from ..utils import SubscribableDict


def PdbInterfaceFactory(
    registry: SubscribableDict,
    pdb_ci_registry: PdbCIRegistry,
    modules_to_trace: Set[str],
) -> Callable[[], PdbInterface]:

    thread_task_id_composer = UniqThreadTaskIdComposer()
    trace_id_counter = count(1).__next__
    prompting_counter = count(1).__next__
    callback_map: WeakKeyDictionary[Any, PdbInterface] = WeakKeyDictionary()

    def callback_func(key):
        callback_map[key].close()

    callback = ThreadTaskDoneCallback(done=callback_func)

    def factory() -> PdbInterface:
        # TODO: check if already created for the same thread or task
        pbi = PdbInterface(
            trace_id_counter=trace_id_counter,
            thread_task_id_composer=thread_task_id_composer,
            registry=registry,
            ci_registry=pdb_ci_registry,
            prompting_counter=prompting_counter,
            modules_to_trace=modules_to_trace,
        )
        key = callback.register()
        callback_map[key] = pbi
        return pbi

    return factory


class PdbInterface:
    """Instantiate Pdb and register its command loops

    TODO: Update parameters

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
        trace_id_counter: Callable[[], int],
        thread_task_id_composer: UniqThreadTaskIdComposer,
        registry: SubscribableDict,
        ci_registry: PdbCIRegistry,
        prompting_counter: Callable[[], int],
        modules_to_trace: Set[str],
    ):
        self._trace_id_counter = trace_id_counter
        self._thread_task_id_composer = thread_task_id_composer
        self._registry = registry
        self._ci_registry = ci_registry
        self._prompting_counter = prompting_counter
        self.modules_to_trace = modules_to_trace
        self._opened = False

    def open(self) -> TraceFunc:
        self._q_stdin: queue.Queue = queue.Queue()
        self._q_stdout: queue.Queue = queue.Queue()

        self._pdb = CustomizedPdb(
            pdbi=self,
            stdin=StreamIn(self._q_stdin),
            stdout=StreamOut(self._q_stdout),
            readrc=False,
        )

        self._trace_id = self._trace_id_counter()
        self._registry[self._trace_id] = None
        ids = (self._registry.get("trace_ids") or ()) + (self._trace_id,)
        self._registry["trace_ids"] = ids

        self._opened = True

        return self._pdb.trace_dispatch

    def close(self):
        if not self._opened:
            return
        del self._registry[self._trace_id]
        ids = list(self._registry.get("trace_ids"))
        ids.remove(self._trace_id)
        ids = tuple(ids)
        self._registry["trace_ids"] = ids

    def calling_trace(self, frame: FrameType, event: str, arg: Any) -> None:
        self._current_trace_args: Optional[Tuple] = (frame, event, arg)

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

        copy = self._state.copy()
        self._registry[self._trace_id] = copy

    def exited_cmdloop(self) -> None:
        self._state["prompting"] = 0

        self._ci_registry.remove(self._trace_id)

        copy = self._state.copy()
        self._registry[self._trace_id] = copy

        self._pdb_ci.end()
