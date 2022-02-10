from itertools import count

from .pdb.proxy import PdbProxy
from .registry import PdbCIRegistry
from .utils import Registry, UniqThreadTaskIdComposer

from typing import Any, Set, Optional
from types import FrameType

from .types import TraceFunc
from .utils.types import ThreadTaskId


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

        pdb_proxy = self.pdb_proxies.get(thread_asynctask_id)
        if not pdb_proxy:
            pdb_proxy = PdbProxy(
                trace=self,
                thread_asynctask_id=thread_asynctask_id,
                modules_to_trace=self.modules_to_trace,
                registry=self.registry,
                ci_registry=self.pdb_ci_registry,
                prompting_counter=self.prompting_counter,
            )
            self.pdb_proxies[thread_asynctask_id] = pdb_proxy

        return pdb_proxy.trace_func(frame, event, arg)

    def returning(self, thread_asynctask_id: ThreadTaskId) -> None:
        self.id_composer.exited(thread_asynctask_id)
        del self.pdb_proxies[thread_asynctask_id]


##__________________________________________________________________||
