from __future__ import annotations
from io import TextIOWrapper
from queue import Queue


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
