from __future__ import annotations

import sys
import os
import signal

from pdb import Pdb

from multiprocessing import Process, Queue
from time import sleep

import pytest

from nextline.process.pdb.stream import StreamIn, StreamOut


def f():
    sleep(0.001)


def run(queue_stdin: Queue[str], queue_stdout: Queue[str]) -> None:
    pdb = Pdb(
        stdin=StreamIn(queue_stdin),
        stdout=StreamOut(queue_stdout),
        readrc=False,
    )
    pdb.reset()
    trace_org = sys.gettrace()
    sys.settrace(pdb.trace_dispatch)
    try:
        f()
    finally:
        sys.settrace(trace_org)
        queue_stdout.put(None)  # type: ignore


def test_one(queue_stdin: Queue[str], queue_stdout: Queue[str]) -> None:

    p = Process(target=run, args=(queue_stdin, queue_stdout))
    p.start()

    print()
    first = True
    while m := queue_stdout.get():
        print(m, end="")
        if m != "(Pdb) ":
            continue
        if first and p.pid:
            os.kill(p.pid, signal.SIGINT)
            first = False
            continue
        command = "next"
        print(command)
        queue_stdin.put(command)

    p.join()


@pytest.fixture
def queue_stdin() -> Queue[str]:
    y: Queue[str] = Queue()
    return y


@pytest.fixture
def queue_stdout() -> Queue[str]:
    y: Queue[str] = Queue()
    return y
