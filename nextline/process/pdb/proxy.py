from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial

from queue import Queue

from ...types import PromptNo, TraceNo
from ...count import PromptNoCounter, TraceNoCounter
from .ci import pdb_command_interface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut


from typing import (
    TYPE_CHECKING,
    Callable,
    Optional,
    Any,
    Tuple,
)
from types import FrameType

if TYPE_CHECKING:
    from sys import _TraceFunc as TraceFunc
    from ..run import Context


def PdbInterfaceTraceFuncFactory(context: Context) -> Callable[[], TraceFunc]:

    trace_no_counter = TraceNoCounter(1)
    prompt_no_counter = PromptNoCounter(1)

    def factory() -> TraceFunc:
        trace_no = trace_no_counter()
        pdbi = PdbInterface(
            trace_no=trace_no,
            context=context,
            prompt_no_counter=prompt_no_counter,
        )
        context["callback"].task_or_thread_start(trace_no, pdbi)
        return pdbi.trace

    return factory


class PdbInterface:
    """Instantiate Pdb and register its command loops"""

    def __init__(
        self,
        trace_no: TraceNo,
        context: Context,
        prompt_no_counter: Callable[[], PromptNo],
    ):
        self._trace_no = trace_no
        self._ci_map = context["pdb_ci_map"]
        self._callback = context["callback"]
        self._opened = False

        q_stdin: Queue[str] = Queue()
        self._q_stdout: Queue[str | None] = Queue()

        self._pdb = CustomizedPdb(
            pdbi=self,
            stdin=StreamIn(q_stdin),
            stdout=StreamOut(self._q_stdout),  # type: ignore
            nosigint=True,
            readrc=False,
        )

        self._trace_args: Optional[Tuple[FrameType, str, Any]] = None

        self._cmd_interface = partial(
            pdb_command_interface,
            trace_no=self._trace_no,
            prompt_no_counter=prompt_no_counter,
            queue_stdin=q_stdin,
            queue_stdout=self._q_stdout,
            callback=context["callback"],
            prompt=self._pdb.prompt,
        )

        self._executor = ThreadPoolExecutor(max_workers=1)

    def trace(self, frame, event, arg) -> Optional[TraceFunc]:
        """Call Pdb while storing trace args"""

        @contextmanager
        def capture(frame, event, arg):
            self._trace_args = (frame, event, arg)
            self._callback.trace_call_start(self._trace_no, self._trace_args)
            try:
                yield
            finally:
                self._trace_args = None
                self._callback.trace_call_end(self._trace_no)

        def create_local_trace() -> TraceFunc:
            next_trace: TraceFunc | None = self._pdb.trace_dispatch

            def local_trace(frame, event, arg) -> Optional[TraceFunc]:
                nonlocal next_trace
                assert next_trace
                with capture(frame, event, arg):
                    if next_trace := next_trace(frame, event, arg):
                        return local_trace
                    return None

            return local_trace

        return create_local_trace()(frame, event, arg)

    def entering_cmdloop(self) -> None:
        """To be called by the custom Pdb before _cmdloop()"""

        if not self._trace_args:
            raise RuntimeError("calling_trace() must be called first")

        wait_prompt, send_command = self._cmd_interface(
            trace_args=self._trace_args,
        )
        self._fut = self._executor.submit(wait_prompt)

        self._ci_map[self._trace_no] = send_command

    def exited_cmdloop(self) -> None:
        """To be called by the custom Pdb after _cmdloop()"""

        del self._ci_map[self._trace_no]
        self._q_stdout.put(None)  # end the thread
        self._fut.result()

    def close(self):
        self._executor.shutdown()
