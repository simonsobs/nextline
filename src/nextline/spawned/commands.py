from dataclasses import dataclass

from nextline.types import PromptNo, TraceNo


@dataclass
class Command:
    pass


@dataclass
class PdbCommand(Command):
    trace_no: TraceNo
    prompt_no: PromptNo
    command: str
