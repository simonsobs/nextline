from __future__ import annotations

from weakref import WeakKeyDictionary

import fnmatch

from typing import TYPE_CHECKING, Any, Set, Dict, Optional, Union, Callable
from types import FrameType

from .pdb.proxy import PdbInterfaceFactory
from .utils import current_task_or_thread

if TYPE_CHECKING:
    from .types import TraceFunc
    from .utils import SubscribableDict
    from .pdb.ci import PdbCommandInterface


MODULES_TO_SKIP = {
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
}


def Trace(
    registry: SubscribableDict,
    pdb_ci_map: Dict[int, PdbCommandInterface],
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

    pdbi_factory = PdbInterfaceFactory(
        registry=registry,
        pdb_ci_map=pdb_ci_map,
        modules_to_trace=modules_to_trace,
    )

    def create_trace_for_single_thread_or_task():
        """To be called in the thread or task to be traced"""
        trace_call_pdb = TraceFromFactory(factory=lambda: pdbi_factory().trace)
        return TraceSelectFirstModule(
            trace=trace_call_pdb,
            modules_to_trace=modules_to_trace,
        )

    return TraceSkipModule(
        skip=MODULES_TO_SKIP,
        trace=TraceSkipLambda(
            trace=TraceAddFirstModule(
                modules_to_trace=modules_to_trace,
                trace=TraceDispatchThreadOrTask(
                    factory=create_trace_for_single_thread_or_task
                ),
            ),
        ),
    )


def TraceSkipModule(trace: TraceFunc, skip: Set[str]) -> TraceFunc:
    def ret(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        module_name = frame.f_globals.get("__name__")
        if _is_matched_to_any(module_name, skip):
            return None
        return trace(frame, event, arg)

    return ret


def TraceSkipLambda(trace: TraceFunc) -> TraceFunc:
    def ret(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        func_name = frame.f_code.co_name
        if func_name == "<lambda>":
            return None
        return trace(frame, event, arg)

    return ret


def TraceAddFirstModule(
    trace: TraceFunc, modules_to_trace: Set[str]
) -> TraceFunc:
    first = True

    def global_trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        if not first:
            return trace(frame, event, arg)

        def create_local_trace() -> TraceFunc:
            next_trace: Union[TraceFunc, None] = trace

            def local_trace(frame, event, arg) -> Optional[TraceFunc]:
                nonlocal first, next_trace
                assert next_trace

                if module_name := frame.f_globals.get("__name__"):
                    first = False
                    modules_to_trace.add(module_name)
                    return trace(frame, event, arg)

                if next_trace := next_trace(frame, event, arg):
                    return local_trace
                return None

            return local_trace

        return create_local_trace()(frame, event, arg)

    return global_trace


def TraceDispatchThreadOrTask(factory: Callable[[], TraceFunc]) -> TraceFunc:
    """Create a trace that creates a new trace for each thread or asyncio task"""

    map: WeakKeyDictionary[Any, TraceFunc] = WeakKeyDictionary()

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

    def ret(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        nonlocal first
        if first:
            module_name = frame.f_globals.get("__name__")
            if not _is_matched_to_any(module_name, modules_to_trace):
                return None
            first = False
        return trace(frame, event, arg)

    return ret


def TraceFromFactory(factory: Callable[[], TraceFunc]) -> TraceFunc:
    """Create a trace that creates a trace first time called

    Useful when desirable to defer the creation until actually called

    It is used to avoid creating instances of Pdb in threads or async tasks
    that are not traced.
    """
    trace: Union[TraceFunc, None] = None

    def global_trace(frame, event, arg) -> Optional[TraceFunc]:
        nonlocal trace
        trace = trace or factory()
        return trace(frame, event, arg)

    return global_trace


def _is_matched_to_any(word: Union[str, None], patterns: Set[str]) -> bool:
    """Test if the word matches any of the patterns

    This function is based on Bdb.is_skipped_module():
    https://github.com/python/cpython/blob/v3.9.5/Lib/bdb.py#L191
    """
    if word is None:
        return False
    for pattern in patterns:
        if fnmatch.fnmatch(word, pattern):
            return True
    return False
