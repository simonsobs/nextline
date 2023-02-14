from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from queue import Queue
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Tuple

from nextline.process.trace.wrap import WithContext
from nextline.types import TraceNo

from .ci import pdb_command_interface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

if TYPE_CHECKING:
    from sys import TraceFunction as TraceFunc  # type: ignore  # noqa: F401

    from nextline.process.run import TraceContext


def PdbInterfaceTraceFuncFactory(context: TraceContext) -> Callable[[], TraceFunc]:
    def factory() -> TraceFunc:
        trace_no_counter = context['trace_no_counter']
        trace_no = trace_no_counter()
        pdbi = PdbInterface(trace_no=trace_no, context=context)
        context["callback"].task_or_thread_start(trace_no)

        trace: TraceFunc = pdbi.trace

        trace = TraceCallCallback(trace=trace, trace_no=trace_no, context=context)
        # TODO: Add a test. The tests pass without the above line.  Without it,
        #       the arrow in the web UI does not move when the Pdb is "continuing."

        return trace

    return factory


def TraceCallCallback(
    trace: TraceFunc, trace_no: TraceNo, context: TraceContext
) -> TraceFunc:

    callback = context['callback']

    @contextmanager
    def _context(frame, event, arg):
        callback.trace_call_start(trace_no, (frame, event, arg))
        try:
            yield
        finally:
            callback.trace_call_end(trace_no)

    return WithContext(trace, context=_context)


class TraceNotCalled(RuntimeError):
    pass


class PdbInterface:
    """Instantiate Pdb and register its command loops"""

    TraceNotCalled = TraceNotCalled

    def __init__(self, trace_no: TraceNo, context: TraceContext):
        self._trace_no = trace_no
        self._ci_map = context["pdb_ci_map"]
        self._callback = context["callback"]
        self._opened = False

        q_stdin: Queue[str] = Queue()
        q_stdout: Queue[str | None] = Queue()

        self._pdb = CustomizedPdb(
            pdbi=self,
            stdin=StreamIn(q_stdin),
            stdout=StreamOut(q_stdout),  # type: ignore
            nosigint=True,
            readrc=False,
        )

        self._trace_args: Optional[Tuple[FrameType, str, Any]] = None

        prompt_no_counter = context['prompt_no_counter']

        self._cmd_interface = partial(
            pdb_command_interface,
            trace_no=self._trace_no,
            prompt_no_counter=prompt_no_counter,
            queue_stdin=q_stdin,
            queue_stdout=q_stdout,
            callback=context["callback"],
            prompt=self._pdb.prompt,
        )

        self._executor = context['executor']

    def trace(self, frame, event, arg) -> Optional[TraceFunc]:
        """Call Pdb while storing trace args"""

        @contextmanager
        def capture(frame, event, arg):
            self._trace_args = (frame, event, arg)
            try:
                yield
            finally:
                self._trace_args = None

        return WithContext(self._pdb.trace_dispatch, context=capture)(frame, event, arg)

    @contextmanager
    def interface_cmdloop(self) -> Generator[None, None, None]:
        '''To be used by CustomizedPdb._cmdloop()'''

        if not self._trace_args:
            msg = f'{self.__class__.__name__}.trace() must be called first.'
            raise self.TraceNotCalled(msg)

        wait, send, end = self._cmd_interface(trace_args=self._trace_args)
        fut = self._executor.submit(wait)
        self._ci_map[self._trace_no] = send

        try:
            yield
        finally:
            del self._ci_map[self._trace_no]
            end()
            fut.result()
