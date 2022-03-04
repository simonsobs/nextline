from __future__ import annotations

import threading

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    def __init__(self, pdb: Pdb, queue_in: Queue, queue_out: Queue):
        self.pdb = pdb
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.ended = False
        self.nprompts = 0

    def send_pdb_command(self, command: str) -> None:
        """send a command to pdb"""
        self.command = command
        self.queue_in.put(command)

    def start(self) -> None:
        """start interfacing the pdb"""
        self.thread = threading.Thread(target=self._receive_pdb_stdout)
        self.thread.start()

    def end(self) -> None:
        """end interfacing the pdb"""
        self.ended = True
        self.queue_out.put(None)  # end the thread
        self.thread.join()

    def _receive_pdb_stdout(self):
        """receive stdout from pdb

        This method runs in its own thread during pdb._cmdloop()
        """
        while out := self._read_until_prompt(self.queue_out, self.pdb.prompt):
            self.nprompts += 1
            self.stdout = out

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
