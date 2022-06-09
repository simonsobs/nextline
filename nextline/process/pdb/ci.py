from __future__ import annotations


from typing import TYPE_CHECKING, Callable, Tuple, Any

from ..callback import Callback
from ...types import PromptNo, TraceNo


if TYPE_CHECKING:
    from types import FrameType
    from queue import Queue


class PdbCommandInterface:
    """Relay pdb command prompts and commands

    An instance of this class is created for each execution of the pdb
    command loop, pdb._cmdloop().
    """

    def __init__(
        self,
        queue_in: Queue[str],
        queue_out: Queue[str | None],
        counter: Callable[[], PromptNo],
        trace_no: TraceNo,
        callback: Callback,
        trace_args: Tuple[FrameType, str, Any],
        prompt="(Pdb) ",
    ):
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._counter = counter
        self._trace_no = trace_no
        self._callback = callback
        self._trace_args = trace_args
        self._prompt = prompt

        self._prompt_no = PromptNo(-1)

    def send_command(self, command: str) -> None:
        """send a command to pdb"""
        self._callback.prompt_end(
            trace_no=self._trace_no, prompt_no=self._prompt_no, command=command
        )
        self._queue_in.put(command)

    def wait_prompt(self) -> None:
        """receive stdout from pdb

        To be run in a thread during pdb._cmdloop()
        """
        while out := _read_until_prompt(self._queue_out, self._prompt):
            self._prompt_no = self._counter()
            self._stdout = out
            self._callback.prompt_start(
                trace_no=self._trace_no,
                prompt_no=self._prompt_no,
                trace_args=self._trace_args,
                out=out,
            )


def _read_until_prompt(queue: Queue[str | None], prompt: str) -> str | None:
    """read the queue up to the prompt"""
    out = ""
    while True:
        m = queue.get()
        if m is None:  # end
            return None
        out += m
        if prompt == m:
            break
    return out
