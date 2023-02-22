from __future__ import annotations

from contextlib import contextmanager
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Tuple

from nextline.process.trace.wrap import WithContext
from nextline.types import TraceNo

from .ci import CmdLoopInterface, pdb_command_interface
from .custom import CustomizedPdb, TraceNotCalled
from .stream import StreamIn, StreamOut

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.run import TraceContext


def PdbInterfaceTraceFuncFactory(context: TraceContext) -> Callable[[], TraceFunc]:
    def factory() -> TraceFunc:
        trace_no_counter = context['trace_no_counter']
        trace_no = trace_no_counter()
        trace = PdbInterface(trace_no=trace_no, context=context)

        # trace: TraceFunc = pdbi.trace

        trace = TraceCallCallback(trace=trace, trace_no=trace_no, context=context)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace

    return factory


def TraceCallCallback(
    trace: TraceFunc, trace_no: TraceNo, context: TraceContext
) -> TraceFunc:

    callback = context['callback']
    callback.task_or_thread_start(trace_no)

    @contextmanager
    def _context(frame, event, arg):
        with callback.trace_call(trace_no, (frame, event, arg)):
            yield

    return WithContext(trace, context=_context)


def PdbInterface(trace_no: TraceNo, context: TraceContext):
    '''
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

    queue_stdin: Queue[str] = Queue()
    queue_stdout: Queue[str | None] = Queue()

    @contextmanager
    def interface_cmdloop() -> Generator[None, None, None]:
        '''To be called in CustomizedPdb._cmdloop()'''

        if not trace_args:
            raise TraceNotCalled(f'{save_trace_args.__name__}() must be called.')

        with pdb_command_interface(
            trace_args=trace_args,
            trace_no=trace_no,
            context=context,
            cmdloop_interface=cmdloop_interface,
            prompt_end=pdb.prompt,
        ):
            yield

    pdb = CustomizedPdb(
        interface_cmdloop=interface_cmdloop,
        stdin=StreamIn(queue_stdin),
        stdout=StreamOut(queue_stdout),  # type: ignore
        nosigint=True,
        readrc=False,
    )

    cmdloop_interface = CmdLoopInterface(
        queue_stdin=queue_stdin, queue_stdout=queue_stdout
    )

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
