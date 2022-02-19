from operator import itemgetter
from itertools import groupby

from unittest.mock import Mock

from typing import Any, Set, List, Tuple, Dict
from types import FrameType


def summarize_trace_calls(mock_trace: Mock) -> Dict[str, Dict[str, Set[str]]]:
    """Traced modules and functions for each event

    e.g., {"module": {"call": {modules}, ...}, "func": {...}}
    """

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
    # sorted by event

    ret = {
        f: {
            k: set(map(itemgetter(f), g))
            for k, g in groupby(args, itemgetter("event"))
        }
        for f in ("module", "func")
    }
    # {"module": {"call": {modules}, ...}, "func": {...}}

    return ret


def trace_call_args(trace: Mock) -> List[Tuple[FrameType, str, Any]]:
    return [call.args for call in trace.call_args_list]
