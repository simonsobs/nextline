from __future__ import annotations

import threading
import datetime

from typing import TYPE_CHECKING, Callable, Tuple, Any

from ..types import PromptInfo

if TYPE_CHECKING:
    from types import FrameType
    from pdb import Pdb
    from queue import Queue
    from ..utils import SubscribableDict


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
        queue_in: Queue,
        queue_out: Queue,
        counter: Callable[[], int],
        trace_id: int,
        registry: SubscribableDict,
        trace_args: Tuple[FrameType, str, Any],
    ):
        self._pdb = pdb
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._counter = counter
        self._trace_id = trace_id
        self._registry = registry
        self._ended = False
        self._nprompts = 0

        frame, event, _ = trace_args
        self._event = event
        self._file_name = pdb.canonic(frame.f_code.co_filename)
        self._line_no = frame.f_lineno
        self._prompt_no = -1

    def send_pdb_command(self, command: str) -> None:
        """send a command to pdb"""
        self._registry["prompt_info"] = PromptInfo(
            run_no=self._registry["run_no"],
            trace_no=self._trace_id,
            prompt_no=self._prompt_no,
            open=False,
            command=command,
            ended_at=datetime.datetime.now(),
        )
        self._command = command
        self._queue_in.put(command)

    def start(self) -> None:
        """start interfacing the pdb"""
        self._thread = threading.Thread(target=self._receive_pdb_stdout)
        self._thread.start()

    def end(self) -> None:
        """end interfacing the pdb"""
        self._ended = True
        self._queue_out.put(None)  # end the thread
        self._thread.join()

    def _receive_pdb_stdout(self):
        """receive stdout from pdb

        This method runs in its own thread during pdb._cmdloop()
        """
        while out := self._read_until_prompt(
            self._queue_out, self._pdb.prompt
        ):
            self._nprompts += 1
            self._prompt_no = self._counter()
            self._stdout = out
            self._registry["prompt_info"] = PromptInfo(
                run_no=self._registry["run_no"],
                trace_no=self._trace_id,
                prompt_no=self._prompt_no,
                open=True,
                event=self._event,
                file_name=self._file_name,
                line_no=self._line_no,
                stdout=out,
                started_at=datetime.datetime.now(),
            )

    def _read_until_prompt(self, queue, prompt):
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
