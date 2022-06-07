from __future__ import annotations
import sys
from contextlib import contextmanager
from typing import Any, ContextManager, TextIO


class CallableContextManager(ContextManager):
    def __call__(self, __s: str) -> Any:
        ...


@contextmanager
def peek_stdout_write(callback: CallableContextManager):
    textio = sys.stdout
    with peek_textio_write(textio, callback) as t:
        yield t


@contextmanager
def peek_stderr_write(callback):
    textio = sys.stderr
    with peek_textio_write(textio, callback) as t:
        yield t


@contextmanager
def peek_textio_write(textio: TextIO, callback: CallableContextManager):
    org_write = textio.write

    def write(s: str, /) -> int:
        callback(s)
        return org_write(s)

    textio.write = write  # type: ignore

    try:
        with callback:
            yield write
    finally:
        textio.write = org_write  # type: ignore
