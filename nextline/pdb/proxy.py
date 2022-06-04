from __future__ import annotations

import dataclasses
import datetime
import queue
from itertools import count

from ..utils import ThreadTaskDoneCallback, current_task_or_thread
from ..types import TraceInfo, PromptInfo
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
    Dict,
    Tuple,
)
from types import FrameType

if TYPE_CHECKING:
    from ..run import Context
    from ..types import TraceFunc
    from ..utils import SubscribableDict


def PdbInterfaceFactory(
    context: Context,
    pdb_ci_map: Dict[int, PdbCommandInterface],
    modules_to_trace: Set[str],
) -> Callable[[], PdbInterface]:
    registry = context["registry"]

    id_composer = context["trace_id_factory"]
    trace_no_counter = count(1).__next__
    prompting_counter = count(1).__next__
    callback_map: Dict[Any, TraceInfo] = {}

    def callback_func(key) -> None:
        trace_info = callback_map[key]
        trace_no = trace_info.trace_no
        key = f"prompt_info_{trace_no}"
        try:
            del registry[key]
        except KeyError:
            pass
        nosl = list(registry.get("trace_nos"))  # type: ignore
        nosl.remove(trace_no)
        nos = tuple(nosl)
        registry["trace_nos"] = nos

        trace_info = dataclasses.replace(
            trace_info,
            state="finished",
            ended_at=datetime.datetime.now(),
        )
        registry["trace_info"] = trace_info

    callback = ThreadTaskDoneCallback(done=callback_func)

    context["callback"] = callback
    # NOTE: Sending `callback` so `callback.close()` can be called when the
    # thread ends.

    def factory() -> PdbInterface:
        trace_no = trace_no_counter()

        nos = (registry.get("trace_nos") or ()) + (trace_no,)
        registry["trace_nos"] = nos

        run_no: int = registry["run_no"]
        thread_task_id = id_composer()

        registry[f"prompt_info_{trace_no}"] = PromptInfo(
            run_no=run_no,
            trace_no=trace_no,
            prompt_no=-1,
            open=False,
        )

        task_or_thread = current_task_or_thread()
        registry["run_no_map"][task_or_thread] = run_no  # type: ignore
        registry["trace_no_map"][task_or_thread] = trace_no  # type: ignore

        trace_info = TraceInfo(
            run_no=run_no,
            trace_no=trace_no,
            thread_no=thread_task_id.thread_no,
            task_no=thread_task_id.task_no,
            state="running",
            started_at=datetime.datetime.now(),
        )
        registry["trace_info"] = trace_info

        key = callback.register()
        callback_map[key] = trace_info

        pbi = PdbInterface(
            trace_id=trace_no,
            registry=registry,
            ci_map=pdb_ci_map,
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
        trace_id: int,
        registry: SubscribableDict,
        ci_map: Dict[int, PdbCommandInterface],
        prompting_counter: Callable[[], int],
        modules_to_trace: Set[str],
    ):
        self._trace_id = trace_id
        self._registry = registry
        self._ci_map = ci_map
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
            trace_id=self._trace_id,
            registry=self._registry,
            trace_args=self._trace_args,
        )
        self._pdb_ci.start()

        self._ci_map[self._trace_id] = self._pdb_ci

    def exited_cmdloop(self) -> None:
        """To be called by the custom Pdb after _cmdloop()"""

        del self._ci_map[self._trace_id]
        self._pdb_ci.end()
