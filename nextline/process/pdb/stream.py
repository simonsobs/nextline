from __future__ import annotations

from io import TextIOWrapper
from queue import Queue
from typing import Generator


class StreamOut(TextIOWrapper):
    def __init__(self, queue: Queue[str]):
        self.queue = queue

    def write(self, s: str, /) -> int:
        self.queue.put(s)
        return len(s)

    def flush(self):
        pass


class StreamIn(TextIOWrapper):
    def __init__(self, queue: Queue[str]):
        self.queue = queue

    def readline(self):
        return self.queue.get()


class CmdLoopInterface:
    def __init__(
        self,
        queue_stdin: Queue[str],
        queue_stdout: Queue[str | None],
        prompt_end: str,  # i.e. '(Pdb) '
    ):
        self._queue_stdin = queue_stdin
        self._queue_stdout = queue_stdout
        self._prompt_end = prompt_end

    def prompts(self) -> Generator[str, str, None]:
        '''Yield each Pdb prompt from stdout.'''
        prompt = ''
        while (msg := self._queue_stdout.get()) is not None:
            prompt += msg
            if self._prompt_end == msg:  # '(Pdb) '
                yield prompt
                prompt = ''

    def issue(self, command: str) -> None:
        self._queue_stdin.put(command)

    def close(self) -> None:
        self._queue_stdout.put(None)
