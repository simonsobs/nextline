from __future__ import annotations
import sys
from contextlib import contextmanager, closing
from typing import TYPE_CHECKING, Any, Protocol, TextIO


if TYPE_CHECKING:
    from contextlib import _SupportsClose

    class WriteWithClose(_SupportsClose, Protocol):
        # https://stackoverflow.com/a/62658919/7309855
        def __call__(self, __s: str) -> Any:
            ...


@contextmanager
def peek_stdout_write(callback_with_close: WriteWithClose):
    textio = sys.stdout
    with peek_textio_write(textio, callback_with_close) as t:
        yield t


@contextmanager
def peek_stderr_write(callback_with_close):
    textio = sys.stderr
    with peek_textio_write(textio, callback_with_close) as t:
        yield t


@contextmanager
def peek_textio_write(textio: TextIO, callback_with_close: WriteWithClose):
    org_write = textio.write

    def write(s: str, /) -> int:
        callback_with_close(s)
        return org_write(s)

    textio.write = write  # type: ignore

    try:
        with closing(callback_with_close):
            yield write
    finally:
        textio.write = org_write  # type: ignore
