from __future__ import annotations

from collections import defaultdict
from types import FrameType
from typing import TYPE_CHECKING, DefaultDict, Dict, Optional, Set

from apluggy import PluginManager, contextmanager

from nextline.process.trace.spec import hookimpl
from nextline.process.trace.types import TraceArgs
from nextline.types import TraceNo

from .with_ import WithContext

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401


class LocalTraceFunc:
    '''A plugin that executes local trace functions.

    It calls different trace functions for each trace number. If a trace
    function doesn't exist for a trace number, this plugin creates a new one by
    calling the hook `create_local_trace_func`.

    A trace number is assigned to each async task or thread by another plugin.
    '''

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook
        self._map: DefaultDict[TraceNo, TraceFunc] = defaultdict(self._create)

    @hookimpl
    def local_trace_func(self, frame: FrameType, event, arg) -> Optional[TraceFunc]:
        trace_no = self._hook.hook.current_trace_no()
        local_trace_func = self._map[trace_no]
        return local_trace_func(frame, event, arg)

    def _create(self) -> TraceFunc:
        '''The factory of the default dict.'''
        trace = self._hook.hook.create_local_trace_func()
        return TraceCallContext(trace=trace, hook=self._hook)


class TraceCallHandler:
    '''A plugin that keeps the trace call arguments during trace calls.

    This plugin collect the trace call arguments when the context manager hook
    `trace_call` is entered. It responds to the first result only hooks
    `is_on_trace_call` and `current_trace_args`.
    '''

    def __init__(self) -> None:
        self._trace_args_map: Dict[TraceNo, TraceArgs] = {}
        self._traces_on_call: Set[TraceNo] = set()

    @hookimpl
    def init(self, hook: PluginManager) -> None:
        self._hook = hook

    @hookimpl
    @contextmanager
    def trace_call(self, trace_args: TraceArgs):
        trace_no = self._hook.hook.current_trace_no()
        self._traces_on_call.add(trace_no)
        self._trace_args_map[trace_no] = trace_args
        try:
            yield
        finally:
            self._traces_on_call.remove(trace_no)
            del self._trace_args_map[trace_no]

    @hookimpl
    def is_on_trace_call(self) -> Optional[bool]:
        trace_no = self._hook.hook.current_trace_no()
        return trace_no in self._traces_on_call

    @hookimpl
    def current_trace_args(self) -> Optional[TraceArgs]:
        trace_no = self._hook.hook.current_trace_no()
        return self._trace_args_map.get(trace_no)


def TraceCallContext(trace: TraceFunc, hook: PluginManager) -> TraceFunc:
    '''Return a trace func that calls the `trace` in the context manager hook `trace_call`.

    When the returned trace function is called, it enters the context manager
    hook `trace_call` with the trace call arguments before calling the `trace`
    function. It exits the context manager after the `trace` function returns.
    '''

    def _context(frame, event, arg):
        return hook.with_.trace_call(trace_args=(frame, event, arg))

    return WithContext(trace, context=_context)
