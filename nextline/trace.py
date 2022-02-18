from __future__ import annotations

from asyncio import isfuture
from itertools import count
from weakref import WeakKeyDictionary

import fnmatch

from typing import Any, Set, Dict, Optional, Union, TYPE_CHECKING
from types import FrameType

from .pdb.proxy import PdbProxy, Registrar, MODULES_TO_SKIP
from .registry import PdbCIRegistry
from .utils import (
    UniqThreadTaskIdComposer,
    TraceDispatchThreadOrTask,
    ThreadTaskDoneCallback,
)

from .types import TraceFunc

if TYPE_CHECKING:
    from .utils import Registry


class RegistrarFactory:
    def __init__(
        self,
        registry: Registry,
        pdb_ci_registry: PdbCIRegistry,
        modules_to_trace: Set[str],
    ):
        self._registry = registry
        self._pdb_ci_registry = pdb_ci_registry
        self._modules_to_trace = modules_to_trace

        self._id_composer = UniqThreadTaskIdComposer()
        self._prompting_counter = count(1).__next__

        self._callback_map: Dict[Any, Registrar] = WeakKeyDictionary()

        def callback_func(key):
            self._callback_map[key].close()

        self._callback = ThreadTaskDoneCallback(done=callback_func)

    def __call__(self) -> Registrar:
        # TODO: check if already created for the same thread or task
        ret = Registrar(
            trace_id=self._id_composer(),
            registry=self._registry,
            ci_registry=self._pdb_ci_registry,
            prompting_counter=self._prompting_counter,
            modules_to_trace=self._modules_to_trace,
        )
        key = self._callback.register()
        self._callback_map[key] = ret
        return ret


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

    create_registrar = RegistrarFactory(
        registry=registry,
        pdb_ci_registry=pdb_ci_registry,
        modules_to_trace=modules_to_trace,
    )

    def create_trace_for_single_thread_or_task():
        """To be called in the thread or task to be traced"""
        registrar = create_registrar()
        pdbproxy = PdbProxy(registrar=registrar)
        return TraceSelectFirstModule(
            trace=pdbproxy,
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
    trace: TraceFunc,
    modules_to_trace: Set[str]
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
