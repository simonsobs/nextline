from dataclasses import dataclass, field
from operator import itemgetter
from itertools import groupby
from keyword import iskeyword

from unittest.mock import Mock

from typing import Any, Set, List, Tuple
from types import FrameType


@dataclass
class TracedScope:
    module: Set[str] = field(default_factory=set)
    func: Set[str] = field(default_factory=set)


@dataclass
class TraceSummary:
    call: TracedScope = field(default_factory=TracedScope)
    line: TracedScope = field(default_factory=TracedScope)
    return_: TracedScope = field(default_factory=TracedScope)
    exception: TracedScope = field(default_factory=TracedScope)
    opcode: TracedScope = field(default_factory=TracedScope)


def summarize_trace_calls(mock_trace: Mock) -> TraceSummary:
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

    ret = TraceSummary(
        **{
            event: TracedScope(
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
