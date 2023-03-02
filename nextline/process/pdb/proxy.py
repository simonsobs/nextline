from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from nextline.process.trace.wrap import WithContext

from .custom import CustomizedPdb
from .stream import StdInOut

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.callback import CallbackForTrace


def TraceCallCallback(trace: TraceFunc, callback: CallbackForTrace) -> TraceFunc:
    @contextmanager
    def _context(frame, event, arg):
        with callback.trace_call(trace_args=(frame, event, arg)):
            yield

    return WithContext(trace, context=_context)


def instantiate_pdb(callback: CallbackForTrace):
    '''Create a new Pdb instance with callback hooked and return its trace function.'''

    stdio = StdInOut(prompt_func=callback.prompt)

    pdb = CustomizedPdb(
        cmdloop_hook=callback.cmdloop,
        stdin=stdio,
        stdout=stdio,
    )
    stdio.prompt_end = pdb.prompt

    return pdb.trace_dispatch
