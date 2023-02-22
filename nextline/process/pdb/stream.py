from __future__ import annotations

from io import TextIOWrapper
from queue import Queue
from typing import Generator, Literal


class StreamOut(TextIOWrapper):
    def __init__(self, queue: Queue[str]):
        self.queue = queue

    def write(self, s: str, /) -> int:
        self.queue.put(s)
        return len(s)

    def flush(self):
        pass


class StreamIn(TextIOWrapper):
    def __init__(self, cli: CmdLoopInterface):
        self._cli = cli

    def readline(self):
        return self._cli.prompt()


class CmdLoopInterface:
    def __init__(self) -> None:

        self._queue_stdin: Queue[str] = Queue()
        self._queue_stdout: Queue[str | None | Literal[True]] = Queue()

        self.stdin = StreamIn(self)
        self.stdout = StreamOut(self._queue_stdout)  # type: ignore

    def prompts(self) -> Generator[str, str, None]:
        '''Yield each prompt from stdout.'''
        prompt = ''
        while (msg := self._queue_stdout.get()) is not None:
            if msg is True:
                yield prompt
                prompt = ''
                continue
            prompt += msg

    def prompt(self) -> str:
        self._queue_stdout.put(True)
        return self._queue_stdin.get()

    def issue(self, command: str) -> None:
        self._queue_stdin.put(command)

    def close(self) -> None:
        self._queue_stdout.put(None)
