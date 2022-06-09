from __future__ import annotations

from concurrent.futures import Executor

from typing import TYPE_CHECKING, Callable, Tuple, Any

from ..callback import Callback
from ...types import PromptNo, TraceNo


if TYPE_CHECKING:
    from types import FrameType
    from pdb import Pdb
    from queue import Queue


class PdbCommandInterface:
    """Relay pdb command prompts and commands

    An instance of this class is created for each execution of the pdb
    command loop, pdb._cmdloop().

    Parameters
    ----------
    pdb : Pdb
        The Pdb instance executing _cmdloop()
    queue_in : queue
        The queue connected to stdin in pdb
    queue_out : queue
        The queue connected to stdout in pdb

    """

    def __init__(
        self,
        pdb: Pdb,
        queue_in: Queue[str],
        queue_out: Queue[str],
        executor: Executor,
        counter: Callable[[], PromptNo],
        trace_no: TraceNo,
        callback: Callback,
        trace_args: Tuple[FrameType, str, Any],
    ):
        self._pdb = pdb
        self._queue_in = queue_in
        self._queue_out: Queue[str | None] = queue_out  # type: ignore
        self._executor = executor
        self._counter = counter
        self._trace_no = trace_no
        self._callback = callback
        self._ended = False
        self._nprompts = 0

        self._trace_args = trace_args
        self._prompt_no = PromptNo(-1)

    def send_pdb_command(self, command: str) -> None:
        """send a command to pdb"""
        self._callback.prompt_end(
            trace_no=self._trace_no, prompt_no=self._prompt_no, command=command
        )
        self._command = command
        self._queue_in.put(command)

    def start(self) -> None:
        """start interfacing the pdb"""
        self._fut = self._executor.submit(self._receive_pdb_stdout)

    def end(self) -> None:
        """end interfacing the pdb"""
        self._ended = True
        self._queue_out.put(None)  # end the thread
        self._fut.result()

    def _receive_pdb_stdout(self) -> None:
        """receive stdout from pdb

        This method runs in its own thread during pdb._cmdloop()
        """
        while out := self._read_until_prompt(
            self._queue_out, self._pdb.prompt
        ):
            self._nprompts += 1
            self._prompt_no = self._counter()
            self._stdout = out
            self._callback.prompt_start(
                trace_no=self._trace_no,
                prompt_no=self._prompt_no,
                trace_args=self._trace_args,
                out=out,
            )

    def _read_until_prompt(
        self, queue: Queue[str | None], prompt: str
    ) -> str | None:
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
