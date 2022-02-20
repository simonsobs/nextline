from dataclasses import dataclass, field
from operator import itemgetter
from itertools import groupby
from keyword import iskeyword

from unittest.mock import Mock

from typing import Any, Set, List, Tuple
from types import FrameType


@dataclass
class TracedScopeType:
    module: Set[str] = field(default_factory=set)
    func: Set[str] = field(default_factory=set)


@dataclass
class TraceSummaryType:
    call: TracedScopeType = field(default_factory=TracedScopeType)
    line: TracedScopeType = field(default_factory=TracedScopeType)
    return_: TracedScopeType = field(default_factory=TracedScopeType)
    exception: TracedScopeType = field(default_factory=TracedScopeType)
    opcode: TracedScopeType = field(default_factory=TracedScopeType)


def summarize_trace_calls(mock_trace: Mock) -> TraceSummaryType:
    """Traced modules and functions for each event"""

    args = trace_call_args(mock_trace)
    # [(frame, event, arg), ...]

    args = [
        {
            "event": event,
            "module": frame.f_globals.get("__name__"),
            "func": frame.f_code.co_name,
        }
        for frame, event, _ in args
    ]
    # [{"event": event, "module": module, "func": func}, ...]

    args = sorted(args, key=itemgetter("event"))
    # sorted for groupby()

    args_by_events = [
        (
            event + ("_" if iskeyword(event) else ""),  # "return_"
            list(args),  # expland to avoid exhaustion below
        )
        for event, args in groupby(args, itemgetter("event"))
    ]

    ret = TraceSummaryType(
        **{
            event: TracedScopeType(
                **{
                    scope: set(map(itemgetter(scope), args))
                    for scope in ("module", "func")
                }
            )
            for event, args in args_by_events
        }
    )
    return ret


def trace_call_args(trace: Mock) -> List[Tuple[FrameType, str, Any]]:
    return [call.args for call in trace.call_args_list]
