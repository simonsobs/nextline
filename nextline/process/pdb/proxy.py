from __future__ import annotations

from contextlib import contextmanager
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Tuple

from nextline.process.trace.wrap import WithContext

from .custom import CustomizedPdb, TraceNotCalled
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

    (This sequence diagram is not up-to-date.)

    trace (WithContext)
      |
      | with
      |--> save_trace_args()
            |
      |<----| yield
      |
      |--------> pdb.trace_dispatch()
                  |
                  |--> pdb._cmdloop()
                        |
                        | with
                        |--> interface_cmdloop()
                              |
                              | with
                              |--> pdb_command_interface()
                                    |
                              |<----| yield
                        |<----| yield
                        |
                        |-------------> pdb.cmdloop()
                                          |
                                          V
                        |<-----------------
                        |
                        |---->| exit
                              |---->| exit
                                    V
                              |<-----
                              V
                        |<-----
                        V
                  |<-----
                  V
      |<-----------
      |
      |---->| exit
            V
      |<-----
      V

    '''

    trace_args: Optional[Tuple[FrameType, str, Any]] = None

    cmdloop_interface = CmdLoopInterface(context=context)

    @contextmanager
    def interface_cmdloop() -> Generator[None, None, None]:
        '''To be called in CustomizedPdb._cmdloop()'''

        if not trace_args:
            raise TraceNotCalled(f'{save_trace_args.__name__}() must be called.')

        with context['callback'].cmdloop(issue=cmdloop_interface.issue):
            yield

    pdb = CustomizedPdb(
        interface_cmdloop=interface_cmdloop,
        stdin=cmdloop_interface.stdin,
        stdout=cmdloop_interface.stdout,
        nosigint=True,
        readrc=False,
    )
    cmdloop_interface.prompt_end = pdb.prompt

    @contextmanager
    def save_trace_args(frame, event, arg):
        '''A context during which Pdb.trace_dispatch() is called.

        Save the args of the trace function so that they can be used in
        interface_cmdloop().
        '''
        nonlocal trace_args
        trace_args = (frame, event, arg)
        try:
            yield
        finally:
            trace_args = None

    return WithContext(pdb.trace_dispatch, context=save_trace_args)
