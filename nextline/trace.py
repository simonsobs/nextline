import asyncio
from itertools import count

from .pdb.proxy import PdbProxy
from .registry import PdbCIRegistry
from .utils import Registry, UniqThreadTaskIdComposer

from typing import Dict, Any, Set, Callable, Optional
from types import FrameType

from .types import TraceFunc
from .utils.types import ThreadTaskId, ThreadID, TaskId


##__________________________________________________________________||
class Trace:
    """The main trace function

    An instance of this class, which is callable, should be set as the
    trace function by sys.settrace() and threading.settrace().

    Parameters
    ----------
    registry : object
        An instance of Registry
    modules_to_trace : set, optional
        The names of modules to trace. The module in which the trace
        is first time called will be always traced even if not in the
        set.

    """

    def __init__(
        self, registry: Registry, modules_to_trace: Optional[Set[str]] = None
    ):

        self.registry = registry
        self.pdb_ci_registry = PdbCIRegistry()

        self.prompting_counter = count(1).__next__

        self.pdb_proxies = {}
        self.trace_thread: Dict[ThreadTaskId, TraceTask] = {}

        if modules_to_trace is None:
            modules_to_trace = set()

        self.modules_to_trace = set(modules_to_trace)
        # Make a copy so that the original won't be modified.
        # self.modules_to_trace will be shared and modified by
        # multiple instances of PdbProxy.

        self.id_composer = UniqThreadTaskIdComposer()

        self.first = True

    def __call__(self, frame: FrameType, event: str, arg: Any) -> TraceFunc:
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        if self.first:
            module_name = frame.f_globals.get("__name__")
            self.modules_to_trace.add(module_name)
            self.first = False

        thread_asynctask_id = self.id_composer.compose()
        # print(*thread_asynctask_id)

        trace_thread = self.trace_thread.get(thread_asynctask_id)
        if not trace_thread:
            pdb_proxy = PdbProxy(
                trace=self,
                thread_asynctask_id=thread_asynctask_id,
                modules_to_trace=self.modules_to_trace,
                registry=self.registry,
                ci_registry=self.pdb_ci_registry,
                prompting_counter=self.prompting_counter,
            )
            trace_thread = TraceTask(
                trace=pdb_proxy.trace_func,
                returning=self.returning,
            )
            self.trace_thread[thread_asynctask_id] = trace_thread

        return trace_thread(frame, event, arg)

        # pdb_proxy = self.pdb_proxies.get(thread_asynctask_id)
        # if not pdb_proxy:
        #     pdb_proxy = PdbProxy(
        #         trace=self,
        #         thread_asynctask_id=thread_asynctask_id,
        #         modules_to_trace=self.modules_to_trace,
        #         registry=self.registry,
        #         ci_registry=self.pdb_ci_registry,
        #         prompting_counter=self.prompting_counter,
        #     )
        #     self.pdb_proxies[thread_asynctask_id] = pdb_proxy

        # return pdb_proxy.trace_func(frame, event, arg)

    def returning(self, *_, **__) -> None:
        thread_asynctask_id = self.id_composer.compose()
        self.id_composer.exited(thread_asynctask_id)
        # del self.pdb_proxies[thread_asynctask_id]
        if thread_asynctask_id not in self.trace_thread:
            return
        del self.trace_thread[thread_asynctask_id]


class TraceTask:
    def __init__(
        self,
        trace: TraceFunc,
        returning: Optional[TraceFunc] = None,
    ):
        self.wrapped = trace
        self.returning = returning

        self._outermost = self.all

        self._first = True
        self._future = False

    def __call__(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """The `call` event"""

        if self._first:
            self._first = False
            return self.outermost(frame, event, arg)
        return self.all(frame, event, arg)

    def outermost(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """The first local scope entered"""

        if self._outermost:
            self._outermost = self._outermost(frame, event, arg)

        if event != "return":
            return self.outermost

        if asyncio.isfuture(arg):
            # awaiting. will be called again
            self._future = True
            return

        if self.returning:
            self.returning(frame, event, arg)

        return

    def all(
        self, frame: FrameType, event: str, arg: Any
    ) -> Optional[TraceFunc]:
        """Every local scope"""

        return self.wrapped(frame, event, arg)
