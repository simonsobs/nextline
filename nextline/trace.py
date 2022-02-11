from __future__ import annotations

import asyncio
from itertools import count
from functools import partial

from .pdb.proxy import PdbProxy
from .registry import PdbCIRegistry
from .utils import UniqThreadTaskIdComposer

from typing import Callable, Dict, Any, Set, Optional, TYPE_CHECKING
from types import FrameType

from .types import TraceFunc
from .utils.types import ThreadTaskId

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

        self.pdb_ci_registry = PdbCIRegistry()

        if modules_to_trace is None:
            modules_to_trace = set()

        self.modules_to_trace = set(modules_to_trace)
        # Make a copy so that the original won't be modified.
        # self.modules_to_trace will be shared and modified by
        # multiple instances of PdbProxy.

        # self.id_composer = UniqThreadTaskIdComposer()

        wrapped_factory = partial(
            PdbProxy,
            trace=self,
            id_composer=UniqThreadTaskIdComposer(),
            modules_to_trace=self.modules_to_trace,
            ci_registry=self.pdb_ci_registry,
            registry=registry,
            prompting_counter=count(1).__next__,
        )

        self.first = True

        self.trace = TraceSingleThreadTask(wrapped_factory=wrapped_factory)

    def __call__(self, frame: FrameType, event: str, arg: Any) -> TraceFunc:
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        if self.first:
            module_name = frame.f_globals.get("__name__")
            self.modules_to_trace.add(module_name)
            self.first = False

        return self.trace(frame, event, arg)


class TraceSingleThreadTask:
    def __init__(self, wrapped_factory: Callable[[], TraceFunc]):

        self.wrapped_factory = wrapped_factory
        self.id_composer = UniqThreadTaskIdComposer()

        self.trace_map: Dict[ThreadTaskId, TraceWithCallback] = {}

    def __call__(self, frame: FrameType, event: str, arg: Any) -> TraceFunc:

        trace_id = self.id_composer.compose()

        trace = self.trace_map.get(trace_id)
        if not trace:
            trace = TraceWithCallback(
                wrapped=self.wrapped_factory(),
                returning=self.returning,
            )
            self.trace_map[trace_id] = trace

        return trace(frame, event, arg)

    def returning(self, *_, **__) -> None:
        trace_id = self.id_composer.compose()
        self.id_composer.exited(trace_id)
        try:
            del self.trace_map[trace_id]
        except KeyError:
            pass


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
        return self.all(frame, event, arg)

    def outermost(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """The first local scope entered"""

        if self._outermost:
            self._outermost = self._outermost(frame, event, arg)

        if event != "return":
            return self.outermost

        if asyncio.isfuture(arg):
            # awaiting. will be called again
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
