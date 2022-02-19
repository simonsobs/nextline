from __future__ import annotations

from asyncio import isfuture
from weakref import WeakKeyDictionary

import fnmatch

from typing import Any, Set, Dict, Optional, Union, Callable, TYPE_CHECKING
from types import FrameType

from .pdb.proxy import PdbInterfaceFactory, PdbInterface, MODULES_TO_SKIP
from .registry import PdbCIRegistry
from .utils import current_task_or_thread

from .types import TraceFunc

if TYPE_CHECKING:
    from .utils import Registry


def Trace(
    registry: Registry,
    pdb_ci_registry: PdbCIRegistry,
    modules_to_trace: Optional[Set[str]] = None,
) -> TraceFunc:
    """Create the main trace function


    Parameters
    ----------
    registry : object
        An instance of Registry
    modules_to_trace : set, optional
        The names of modules to trace. The module in which the trace
        is first time called will be always traced even if not in the
        set.

    """

    if modules_to_trace is None:
        modules_to_trace = set()

    modules_to_trace = set(modules_to_trace)
    # Make a copy so that the original won't be modified.
    # modules_to_trace will be shared and modified by
    # multiple objects.

    create_pdbi = PdbInterfaceFactory(
        registry=registry,
        pdb_ci_registry=pdb_ci_registry,
        modules_to_trace=modules_to_trace,
    )

    def create_trace_for_single_thread_or_task():
        """To be called in the thread or task to be traced"""
        pdbi = create_pdbi()
        trace_call_pdb = TraceCallPdb(pdbi=pdbi)
        return TraceSelectFirstModule(
            trace=trace_call_pdb,
            modules_to_trace=modules_to_trace,
        )

    return TraceAddFirstModule(
        trace=TraceSkipModule(
            trace=TraceSkipLambda(
                trace=TraceDispatchThreadOrTask(
                    factory=create_trace_for_single_thread_or_task
                )
            )
        ),
        modules_to_trace=modules_to_trace,
    )


def TraceAddFirstModule(
    trace: TraceFunc, modules_to_trace: Set[str]
) -> TraceFunc:
    first = True

    def ret(frame, event, arg) -> Optional[TraceFunc]:
        nonlocal first
        if first:
            module_name = frame.f_globals.get("__name__")
            modules_to_trace.add(module_name)
            first = False

        return trace(frame, event, arg)

    return ret


def TraceSkipModule(
    trace: TraceFunc,
    skip: Set[str] = MODULES_TO_SKIP,
) -> TraceFunc:
    def ret(frame, event, arg) -> Optional[TraceFunc]:
        module_name = frame.f_globals.get("__name__")
        if is_matched_to_any(module_name, skip):
            return
        return trace(frame, event, arg)

    return ret


def TraceSkipLambda(trace: TraceFunc) -> TraceFunc:
    def ret(frame, event, arg) -> Optional[TraceFunc]:
        func_name = frame.f_code.co_name
        if func_name == "<lambda>":
            return
        return trace(frame, event, arg)

    return ret


def TraceDispatchThreadOrTask(factory: Callable[[], TraceFunc]) -> TraceFunc:
    """Create a trace that creates a new trace for each thread or asyncio task"""

    map: Dict[Any, TraceFunc] = WeakKeyDictionary()

    def ret(frame, event, arg) -> Optional[TraceFunc]:
        key = current_task_or_thread()
        trace = map.get(key)
        if not trace:
            trace = factory()
            map[key] = trace
        return trace(frame, event, arg)

    return ret


def TraceSelectFirstModule(
    trace: TraceFunc,
    modules_to_trace: Set[str],
) -> TraceFunc:
    first = True

    def ret(frame, event, arg) -> Optional[TraceFunc]:
        nonlocal first
        if first:
            module_name = frame.f_globals.get("__name__")
            if not is_matched_to_any(module_name, modules_to_trace):
                return
            first = False
        return trace(frame, event, arg)

    return ret


def TraceCallPdb(pdbi: PdbInterface) -> TraceFunc:

    pdb_trace: Union[TraceFunc, None] = None
    # Instead of calling pdbi.open() here, set initially None so that
    # pdbi.open() won't be called unless global_trace() is actually
    # called.

    def global_trace(frame, event, arg) -> Optional[TraceFunc]:
        nonlocal pdb_trace
        if not pdb_trace:
            pdb_trace = pdbi.open()  # Bdb.trace_dispatch

        def create_local_trace():
            next_trace: Union[TraceFunc, None] = pdb_trace

            def local_trace(frame, event, arg):
                nonlocal next_trace
                pdbi.calling_trace(frame, event, arg)
                next_trace = next_trace(frame, event, arg)
                pdbi.exited_trace()
                if next_trace:
                    return local_trace

            return local_trace

        return create_local_trace()(frame, event, arg)

    return global_trace


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
