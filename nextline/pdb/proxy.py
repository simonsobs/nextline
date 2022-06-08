from __future__ import annotations

import queue
from itertools import count

from ..types import PromptNo, TraceNo
from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut


from typing import (
    TYPE_CHECKING,
    Callable,
    Optional,
    Union,
    Any,
    Set,
    Tuple,
)
from types import FrameType

if TYPE_CHECKING:
    from ..run import Context
    from sys import _TraceFunc as TraceFunc


def PdbInterfaceFactory(
    context: Context,
    modules_to_trace: Set[str],
) -> Callable[[], PdbInterface]:

    # trace_no_counter = count(1).__next__
    trace_no_counter = (lambda f: (lambda: TraceNo(f())))(count(1).__next__)

    # prompting_counter = count(1).__next__
    prompting_counter = (lambda f: (lambda: PromptNo(f())))(count(1).__next__)

    def factory() -> PdbInterface:
        trace_no = trace_no_counter()
        context["callback"].trace_start(trace_no)

        pbi = PdbInterface(
            trace_no=trace_no,
            context=context,
            prompting_counter=prompting_counter,
            modules_to_trace=modules_to_trace,
        )
        return pbi

    return factory


class PdbInterface:
    """Instantiate Pdb and register its command loops

    TODO: Update parameters

    Parameters
    ----------
    trace_id : object
        The Id to distinguish each instance of Pdb
    modules_to_trace: set
        The set of modules to trace. This object is shared by multiple
        objects. Modules in which Pdb commands are prompted will be
        added.
    registry: object
        A registry
    ci_map: object
        A registry
    prompting_counter : callable
        Used to count the Pdb command loops
    """

    def __init__(
        self,
        trace_no: int,
        context: Context,
        prompting_counter: Callable[[], PromptNo],
        modules_to_trace: Set[str],
    ):
        self._trace_no = trace_no
        self._context = context
        self._ci_map = context["pdb_ci_map"]
        self._prompting_counter = prompting_counter
        self.modules_to_trace = modules_to_trace
        self._opened = False

        self._q_stdin: queue.Queue = queue.Queue()
        self._q_stdout: queue.Queue = queue.Queue()

        self._pdb = CustomizedPdb(
            pdbi=self,
            stdin=StreamIn(self._q_stdin),
            stdout=StreamOut(self._q_stdout),
            readrc=False,
        )

        self._trace_args: Optional[Tuple[FrameType, str, Any]] = None

    def trace(self, frame, event, arg) -> Optional[TraceFunc]:
        """Call Pdb while storing trace args"""

        def calling_trace(frame, event, arg) -> None:
            self._trace_args = (frame, event, arg)

        def exited_trace() -> None:
            self._trace_args = None

        def create_local_trace() -> TraceFunc:
            pdb_trace: Union[TraceFunc, None] = self._pdb.trace_dispatch

            def local_trace(frame, event, arg) -> Optional[TraceFunc]:
                nonlocal pdb_trace
                assert pdb_trace
                calling_trace(frame, event, arg)
                try:
                    if pdb_trace := pdb_trace(frame, event, arg):
                        return local_trace
                    return None
                finally:
                    exited_trace()

            return local_trace

        return create_local_trace()(frame, event, arg)

    def entering_cmdloop(self) -> None:
        """To be called by the custom Pdb before _cmdloop()"""

        if not self._trace_args:
            raise RuntimeError("calling_trace() must be called first")

        frame, *_ = self._trace_args

        if module_name := frame.f_globals.get("__name__"):
            # TODO: This should be done somewhere else
            self.modules_to_trace.add(module_name)

        self._pdb_ci = PdbCommandInterface(
            pdb=self._pdb,
            queue_in=self._q_stdin,
            queue_out=self._q_stdout,
            counter=self._prompting_counter,
            trace_no=self._trace_no,
            context=self._context,
            trace_args=self._trace_args,
        )
        self._pdb_ci.start()

        self._ci_map[self._trace_no] = self._pdb_ci

    def exited_cmdloop(self) -> None:
        """To be called by the custom Pdb after _cmdloop()"""

        del self._ci_map[self._trace_no]
        self._pdb_ci.end()
