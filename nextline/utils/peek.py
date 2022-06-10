from __future__ import annotations
import sys
from contextlib import contextmanager
from typing import Any, Callable, TextIO


@contextmanager
def peek_stdout(callback: Callable[[str], Any]):
    textio = sys.stdout
    with peek_textio(textio, callback) as t:
        yield t


@contextmanager
def peek_stderr(callback: Callable[[str], Any]):
    textio = sys.stderr
    with peek_textio(textio, callback) as t:
        yield t


@contextmanager
def peek_textio(textio: TextIO, callback: Callable[[str], Any]):
    org_write = textio.write

    def write(s: str, /) -> int:
        callback(s)
        return org_write(s)

    textio.write = write  # type: ignore

    try:
        yield write
    finally:
        textio.write = org_write  # type: ignore
