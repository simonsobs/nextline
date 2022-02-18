from __future__ import annotations

from threading import Thread
from asyncio import Task, isfuture
from itertools import count
from weakref import WeakKeyDictionary

from .pdb.proxy import (
    PdbProxy,
    Registrar,
    TraceSkipModule,
    TraceSkipLambda,
    TraceSelectFirstModule,
)
from .registry import PdbCIRegistry
from .utils import (
    UniqThreadTaskIdComposer,
    TraceDispatchThreadOrTask,
    ThreadTaskDoneCallback,
)

from typing import Any, Set, Dict, Optional, Union, TYPE_CHECKING
from types import FrameType

from .types import TraceFunc

if TYPE_CHECKING:
    from .utils import Registry


##__________________________________________________________________||
class Trace:
    """The main trace function

    An instance of this class, which is callable, should be set as the
    trace function by sys.settrace() and threading.settrace().

    Parameters
    ----------
    registry : object
        An instance of Registry
    modules_to_trace : set, optional
        The names of modules to trace. The module in which the trace
        is first time called will be always traced even if not in the
        set.

    """

    def __init__(
        self, registry: Registry, modules_to_trace: Optional[Set[str]] = None
    ):

        self._registry = registry
        self.pdb_ci_registry = PdbCIRegistry()

        if modules_to_trace is None:
            modules_to_trace = set()

        self.modules_to_trace = set(modules_to_trace)
        # Make a copy so that the original won't be modified.
        # self.modules_to_trace will be shared and modified by
        # multiple instances of PdbProxy.

        self._id_composer = UniqThreadTaskIdComposer()
        self._prompting_counter = count(1).__next__

        self._registrar_map: Dict[
            Union[Task, Thread], Registrar
        ] = WeakKeyDictionary()

        self._handle = ThreadTaskDoneCallback(done=self._callback)

        self.first = True

        self.trace = TraceSkipModule(
            trace=TraceSkipLambda(
                trace=TraceDispatchThreadOrTask(factory=self._create_trace)
            )
        )

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        if self.first:
            module_name = frame.f_globals.get("__name__")
            self.modules_to_trace.add(module_name)
            self.first = False

        return self.trace(frame, event, arg)

    def _create_trace(self):

        registrar = Registrar(
            trace_id=self._id_composer(),
            registry=self._registry,
            ci_registry=self.pdb_ci_registry,
            prompting_counter=self._prompting_counter,
            modules_to_trace=self.modules_to_trace,
        )

        pdbproxy = PdbProxy(registrar=registrar)

        task_or_thread = self._handle.register()
        self._registrar_map[task_or_thread] = registrar

        trace = TraceSelectFirstModule(
            trace=pdbproxy,
            modules_to_trace=self.modules_to_trace,
        )

        return trace

    def _callback(self, task_or_thread: Union[Task, Thread]):
        self._registrar_map[task_or_thread].close()


class TraceWithCallback:
    def __init__(
        self,
        wrapped: TraceFunc,
        returning: Optional[TraceFunc] = None,
    ):
        self.wrapped = wrapped
        self.returning = returning

        self._outermost = self.all

        self._first = True
        self._future = False

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """The `call` event"""

        if self._first:
            self._first = False
            return self.outermost(frame, event, arg)
        if self._future:
            self._future = False
            self._outermost = self.all
            return self.outermost(frame, event, arg)
        return self.all(frame, event, arg)

    def outermost(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """The first local scope entered"""

        if self._outermost:
            self._outermost = self._outermost(frame, event, arg)

        if event != "return":
            return self.outermost

        if isfuture(arg):
            # awaiting. will be called again

            # NOTE: This doesn't detect all `await`. Some `await`
            # returns without any arg, for example, the sleep with
            # the delay 0, i.e., asyncio.sleep(0)
            self._future = True
            return

        if self.returning:
            self.returning(frame, event, arg)

        return

    def all(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """Every local scope"""

        return self.wrapped(frame, event, arg)
