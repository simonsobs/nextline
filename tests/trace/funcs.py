from dataclasses import dataclass, field
from operator import itemgetter
from itertools import groupby
from keyword import iskeyword

from unittest.mock import Mock

from typing import Optional, Any, List, Tuple, Set, Dict
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


def summarize_trace_calls(
    mock_trace: Mock,
    modules: Optional[Set[str]] = None,
) -> TraceSummary:
    """Traced modules and functions for each event"""

    args_ = trace_call_args(mock_trace)  # type: ignore
    # [(frame, event, arg), ...]

    args = [
        {
            "event": event,
            "module": frame.f_globals.get("__name__"),
            "func": frame.f_code.co_name,
        }
        for frame, event, _ in args_
    ]
    # [{"event": event, "module": module, "func": func}, ...]

    if modules is not None:
        args = [d for d in args if d["module"] in modules]

    args = sorted(args, key=itemgetter("event"))
    # sorted for groupby()

    args_by_events = [
        (
            event + ("_" if iskeyword(event) else ""),  # "return_"
            list(args),  # expand to avoid exhaustion below
        )
        for event, args in groupby(args, itemgetter("event"))
    ]

    ret = TraceSummary(
        **{
            event: TracedScope(
                **{
                    scope: ordered_uniq_values(args, scope)
                    for scope in ("module", "func")
                }
            )
            for event, args in args_by_events
        }
    )
    return ret


def ordered_uniq_values(dicts: List[Dict], key: Any) -> List:
    """List of unique values of dicts for the key

    Note: The order is preserved while consecutive duplicates are removed.
    """
    return [v for v, _ in groupby([d[key] for d in dicts])]


def trace_call_args(trace: Mock) -> List[Tuple[FrameType, str, Any]]:
    return [call.args for call in trace.call_args_list]
