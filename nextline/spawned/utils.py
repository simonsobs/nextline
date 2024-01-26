from types import FrameType
from typing import Any, Callable, ContextManager, Optional

from .types import TraceFunction


def WithContext(
    trace: TraceFunction, context: Callable[[FrameType, str, Any], ContextManager[None]]
) -> TraceFunction:
    '''Return a new trace func that calls the given trace func in the context.'''

    def _create_local_trace() -> TraceFunction:
        next_trace: TraceFunction | None = trace

        def _local_trace(
            frame: FrameType, event: str, arg: Any
        ) -> Optional[TraceFunction]:
            nonlocal next_trace
            assert next_trace
            with context(frame, event, arg):
                if next_trace := next_trace(frame, event, arg):
                    return _local_trace
                return None

        return _local_trace

    def _global_trace(
        frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunction]:
        return _create_local_trace()(frame, event, arg)

    return _global_trace
