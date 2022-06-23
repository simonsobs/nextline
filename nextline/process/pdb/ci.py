from __future__ import annotations

from types import FrameType
from queue import Queue
from typing import Callable, Tuple, Any

from ..callback import Callback
from ...types import TraceNo, PromptNo


def pdb_command_interface(
    trace_args: Tuple[FrameType, str, Any],
    trace_no: TraceNo,
    prompt_no_counter: Callable[[], PromptNo],
    queue_stdin: Queue[str],
    queue_stdout: Queue[str | None],
    callback: Callback,
    prompt="(Pdb) ",
) -> Tuple[Callable[[], None], Callable[[str, PromptNo], None]]:

    _prompt_no: PromptNo

    def wait_prompt() -> None:
        """receive stdout from pdb

        To be run in a thread during pdb._cmdloop()
        """
        nonlocal _prompt_no
        while out := _read_until_prompt(queue_stdout, prompt):
            _prompt_no = prompt_no_counter()
            # print(_prompt_no)
            callback.prompt_start(
                trace_no=trace_no,
                prompt_no=_prompt_no,
                trace_args=trace_args,
                out=out,
            )

    def send_command(command: str, prompt_no: PromptNo) -> None:
        """send a command to pdb"""
        callback.prompt_end(
            trace_no=trace_no, prompt_no=prompt_no, command=command
        )
        queue_stdin.put(command)

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
