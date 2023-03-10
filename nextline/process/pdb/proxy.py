from __future__ import annotations

from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, ContextManager, Optional

from .custom import CustomizedPdb
from .stream import StdInOut

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.trace.plugins.local_ import PromptFunc


def WithContext(
    trace: TraceFunc, context: Callable[[FrameType, str, Any], ContextManager[None]]
) -> TraceFunc:
    def _create_local_trace() -> TraceFunc:
        next_trace: TraceFunc | None = trace

        def _local_trace(frame, event, arg) -> Optional[TraceFunc]:
            nonlocal next_trace
            assert next_trace
            with context(frame, event, arg):
                if next_trace := next_trace(frame, event, arg):
                    return _local_trace
                return None

        return _local_trace

    def _global_trace(frame: FrameType, event, arg) -> Optional[TraceFunc]:
        return _create_local_trace()(frame, event, arg)

    return _global_trace


def instantiate_pdb(callback: PromptFunc):
    '''Create a new Pdb instance with callback hooked and return its trace function.'''

    stdio = StdInOut(prompt_func=callback.prompt)

    pdb = CustomizedPdb(
        cmdloop_hook=callback.cmdloop,
        stdin=stdio,
        stdout=stdio,
    )
    stdio.prompt_end = pdb.prompt

    return pdb.trace_dispatch
