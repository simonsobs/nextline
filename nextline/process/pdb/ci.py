from __future__ import annotations

from types import FrameType
from queue import Queue
from typing import Callable, Tuple, Any

from ..callback import Callback
from ...types import TraceNo, PromptNo


def pdb_command_interface(
    queue_in: Queue[str],
    queue_out: Queue[str | None],
    counter: Callable[[], PromptNo],
    trace_no: TraceNo,
    callback: Callback,
    trace_args: Tuple[FrameType, str, Any],
    prompt="(Pdb) ",
) -> Tuple[Callable[[], None], Callable[[str], None]]:

    prompt_no = PromptNo(-1)

    def wait_prompt() -> None:
        """receive stdout from pdb

        To be run in a thread during pdb._cmdloop()
        """
        nonlocal prompt_no
        while out := _read_until_prompt(queue_out, prompt):
            prompt_no = counter()
            callback.prompt_start(
                trace_no=trace_no,
                prompt_no=prompt_no,
                trace_args=trace_args,
                out=out,
            )

    def send_command(command: str) -> None:
        """send a command to pdb"""
        callback.prompt_end(
            trace_no=trace_no, prompt_no=prompt_no, command=command
        )
        queue_in.put(command)

    return wait_prompt, send_command


def _read_until_prompt(queue: Queue[str | None], prompt: str) -> str | None:
    """read the queue up to the prompt"""
    out = ""
    while (m := queue.get()) is not None:
        out += m
        if prompt == m:
            break
    else:
        return None

    return out
