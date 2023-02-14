from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Tuple

from nextline.process.trace.wrap import WithContext
from nextline.types import TraceNo

from .ci import pdb_command_interface
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
        callback.trace_call_start(trace_no, (frame, event, arg))
        try:
            yield
        finally:
            callback.trace_call_end(trace_no)

    return WithContext(trace, context=_context)


def PdbInterface(trace_no: TraceNo, context: TraceContext):

    _ci_map = context["pdb_ci_map"]

    q_stdin: Queue[str] = Queue()
    q_stdout: Queue[str | None] = Queue()

    _trace_args: Optional[Tuple[FrameType, str, Any]] = None

    @contextmanager
    def interface_cmdloop() -> Generator[None, None, None]:
        '''To be used by CustomizedPdb._cmdloop()'''

        if not _trace_args:
            msg = 'trace() must be called first.'
            raise TraceNotCalled(msg)

        wait, send, end = _cmd_interface(trace_args=_trace_args)
        fut = context['executor'].submit(wait)
        _ci_map[trace_no] = send

        try:
            yield
        finally:
            del _ci_map[trace_no]
            end()
            fut.result()

    _pdb = CustomizedPdb(
        interface_cmdloop=interface_cmdloop,
        stdin=StreamIn(q_stdin),
        stdout=StreamOut(q_stdout),  # type: ignore
        nosigint=True,
        readrc=False,
    )

    _cmd_interface = partial(
        pdb_command_interface,
        trace_no=trace_no,
        prompt_no_counter=context['prompt_no_counter'],
        queue_stdin=q_stdin,
        queue_stdout=q_stdout,
        callback=context['callback'],
        prompt=_pdb.prompt,
    )

    @contextmanager
    def capture(frame, event, arg):
        nonlocal _trace_args
        _trace_args = (frame, event, arg)
        try:
            yield
        finally:
            _trace_args = None

    return WithContext(_pdb.trace_dispatch, context=capture)
