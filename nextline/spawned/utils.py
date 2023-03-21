from __future__ import annotations

import os
from types import FrameType
from typing import Any, Callable, ContextManager, Dict, Optional

from .types import TraceFunction


def WithContext(
    trace: TraceFunction, context: Callable[[FrameType, str, Any], ContextManager[None]]
) -> TraceFunction:
    '''Return a new trace func that calls the given trace func in the context.'''

    def _create_local_trace() -> TraceFunction:
        next_trace: TraceFunction | None = trace

        def _local_trace(frame, event, arg) -> Optional[TraceFunction]:
            nonlocal next_trace
            assert next_trace
            with context(frame, event, arg):
                if next_trace := next_trace(frame, event, arg):
                    return _local_trace
                return None

        return _local_trace

    def _global_trace(frame: FrameType, event, arg) -> Optional[TraceFunction]:
        return _create_local_trace()(frame, event, arg)

    return _global_trace


def ToCanonicPath() -> Callable[[str], str]:
    # Based on Bdb.canonic()
    # https://github.com/python/cpython/blob/v3.10.5/Lib/bdb.py#L39-L54

    cache: Dict[str, str] = {}

    def _to_canonic_path(filename: str) -> str:
        if filename == "<" + filename[1:-1] + ">":
            return filename
        canonic = cache.get(filename)
        if not canonic:
            canonic = os.path.abspath(filename)
            canonic = os.path.normcase(canonic)
            cache[filename] = canonic
        return canonic

    return _to_canonic_path


to_canonic_path = ToCanonicPath()
