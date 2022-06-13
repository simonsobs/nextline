from __future__ import annotations

from dataclasses import dataclass, field
from operator import itemgetter, attrgetter
from itertools import groupby
from keyword import iskeyword

from unittest.mock import Mock

from typing import (
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Any,
    List,
    Tuple,
    Set,
    TypedDict,
)
from types import FrameType


@dataclass
class TracedScope:
    module: List[str] = field(default_factory=list)
    func: List[str] = field(default_factory=list)


@dataclass
class TraceSummary:
    call: TracedScope = field(default_factory=TracedScope)
    line: TracedScope = field(default_factory=TracedScope)
    return_: TracedScope = field(default_factory=TracedScope)
    exception: TracedScope = field(default_factory=TracedScope)
    opcode: TracedScope = field(default_factory=TracedScope)


class _S(TypedDict):
    event: str
    module: str
    func: str


def summarize_trace_calls(
    mock_trace: Mock,
    modules: Optional[Set[str]] = None,
) -> TraceSummary:
    """Traced modules and functions for each event"""

    args_ = trace_call_args(mock_trace)
    # ((frame, event, arg), ...)

    args = (
        _S(
            event=event,
            module=frame.f_globals.get("__name__", ""),
            func=frame.f_code.co_name,
        )
        for frame, event, _ in args_
    )
    # [{"event": event, "module": module, "func": func}, ...]

    if modules is not None:
        args = (d for d in args if d["module"] in modules)

    args_sorted = sorted(args, key=itemgetter("event"))
    # sort for groupby()

    args_by_events = [
        (
            event + ("_" if iskeyword(event) else ""),  # "return_"
            list(args),  # expand to avoid exhaustion below
        )
        for event, args in groupby(args_sorted, itemgetter("event"))
    ]

    ret = TraceSummary(
        **{
            event: TracedScope(
                **{
                    scope: list(ordered_uniq_values(args, scope))  # type: ignore
                    for scope in ("module", "func")
                }
            )
            for event, args in args_by_events
        }
    )
    return ret


def ordered_uniq_values(
    dicts: Iterable[Mapping[str, str]], key: str
) -> Iterator[str]:
    """List of unique values of dicts for the key

    Note: The order is preserved while consecutive duplicates are removed.
    """
    return (v for v, _ in groupby([d[key] for d in dicts]))


def trace_call_args(trace: Mock) -> Iterator[Tuple[FrameType, str, Any]]:
    return map(attrgetter("args"), trace.call_args_list)
