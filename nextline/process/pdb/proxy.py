from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable

from nextline.process.callback import Callback
from nextline.process.trace.wrap import WithContext

from .custom import CustomizedPdb
from .stream import StdInOut

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.run import TraceContext


def PdbInterfaceTraceFuncFactory(context: TraceContext) -> Callable[[], TraceFunc]:
    def factory() -> TraceFunc:

        callback = context['callback']
        callback.task_or_thread_start()
        trace = instantiate_pdb(callback=callback)

        trace = TraceCallCallback(trace=trace, callback=callback)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace

    return factory


def TraceCallCallback(trace: TraceFunc, callback: Callback) -> TraceFunc:
    @contextmanager
    def _context(frame, event, arg):
        with callback.trace_call(trace_args=(frame, event, arg)):
            yield

    return WithContext(trace, context=_context)


def instantiate_pdb(callback: Callback):
    '''Create a new Pdb instance with callback hooked and return its trace function.'''

    stdio = StdInOut(prompt_func=callback.prompt)

    pdb = CustomizedPdb(
        cmdloop_hook=callback.cmdloop,
        stdin=stdio,
        stdout=stdio,
    )
    stdio.prompt_end = pdb.prompt

    return pdb.trace_dispatch
