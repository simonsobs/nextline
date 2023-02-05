from queue import Queue  # noqa F401
from typing import Any, Callable, MutableMapping, Tuple, TypedDict  # noqa F401

from typing_extensions import TypeAlias

from nextline.types import PromptNo, RunNo, TraceNo

PdbCommand: TypeAlias = str
QueueCommands: TypeAlias = "Queue[Tuple[PdbCommand, PromptNo, TraceNo] | None]"
QueueRegistry: TypeAlias = "Queue[Tuple[str, Any, bool]]"
PdbCiMap: TypeAlias = MutableMapping[TraceNo, Callable[[PdbCommand, PromptNo], Any]]


class RunArg(TypedDict):
    run_no: RunNo
    statement: str
    filename: str
