import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable, ContextManager, TextIO


def peek_stdout(callback: Callable[[str], Any]) -> ContextManager[Callable[[str], int]]:
    '''A context manager that executes the callback with text written to stdout.

    Example:

    Collect arguments to the callback in this list:
    >>> written = []

    Define a callback that appends the argument to the list:
    >>> def callback(s: str) -> None:
    ...     written.append(s)

    Write to stdout in a context:
    >>> with peek_stdout(callback):
    ...     print('hello')
    ...     print('world')
    hello
    world

    The callback was called with the text written to stdout:
    >>> print(''.join(written), end='')
    hello
    world


    NOTE: Do not write to stdout in the callback. This will cause an infinite recursion.

    '''
    return peek_textio(sys.stdout, callback)


def peek_stderr(callback: Callable[[str], Any]) -> ContextManager[Callable[[str], int]]:
    '''A context manager that executes the callback with text written to stderr.'''
    return peek_textio(sys.stderr, callback)


@contextmanager
def peek_textio(
    textio: TextIO, callback: Callable[[str], Any]
) -> Iterator[Callable[[str], int]]:
    '''A context manager that executes the callback with text written to the textio.'''

    org_write = textio.write

    def write(s: str, /) -> int:
        callback(s)
        return org_write(s)

    textio.write = write  # type: ignore

    try:
        yield write
    finally:
        textio.write = org_write  # type: ignore
