from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable

from nextline.process.trace.wrap import WithContext

from .custom import CustomizedPdb
from .stream import CmdLoopInterface

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.run import TraceContext


def PdbInterfaceTraceFuncFactory(context: TraceContext) -> Callable[[], TraceFunc]:
    def factory() -> TraceFunc:

        callback = context['callback']
        callback.task_or_thread_start()
        trace = PdbInterface(context=context)

        trace = TraceCallCallback(trace=trace, context=context)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace

    return factory


def TraceCallCallback(trace: TraceFunc, context: TraceContext) -> TraceFunc:
    callback = context['callback']

    @contextmanager
    def _context(frame, event, arg):
        with callback.trace_call(trace_args=(frame, event, arg)):
            yield

    return WithContext(trace, context=_context)


def PdbInterface(context: TraceContext):
    '''
    pdb.trace_dispatch()
     |
     |--> pdb.cmdloop()
           |
           | with
           |--> cmdloop_hook()
                 |
           |<----| yield
           |
           | super
           |--------> pdb.cmdloop()
                       |
                       V
           |<-----------
           |
           |---->| exit
                 V
           |<-----
           V
     |<-----
     V

    '''

    cmdloop_interface = CmdLoopInterface(context=context)

    pdb = CustomizedPdb(
        cmdloop_hook=context['callback'].cmdloop,
        stdin=cmdloop_interface.stdin,
        stdout=cmdloop_interface.stdout,
    )
    cmdloop_interface.prompt_end = pdb.prompt

    return pdb.trace_dispatch
