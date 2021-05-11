from .pdb.proxy import PdbProxy
from .registry import PdbCIRegistry
from .utils import UniqThreadTaskIdComposer

##__________________________________________________________________||
class Trace:
    """The main trace function

    An instance of this class, which is callable, should be set as the
    trace function by sys.settrace() and threading.settrace().

    """
    def __init__(self, registry):

        self.registry = registry
        self.pdb_ci_registry = PdbCIRegistry()

        self.pdb_proxies = {}

        self.modules_to_trace = {'nextline.main'}

        self.id_composer = UniqThreadTaskIdComposer()

    def __call__(self, frame, event, arg):
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        thread_asynctask_id = self.id_composer.compose()
        # print(*thread_asynctask_id)

        pdb_proxy = self.pdb_proxies.get(thread_asynctask_id)
        if not pdb_proxy:
            pdb_proxy = PdbProxy(
                trace=self,
                thread_asynctask_id=thread_asynctask_id,
                modules_to_trace=self.modules_to_trace,
                registry=self.registry,
                ci_registry=self.pdb_ci_registry
            )
            self.pdb_proxies[thread_asynctask_id] = pdb_proxy

        return pdb_proxy.trace_func(frame, event, arg)

    def returning(self, thread_asynctask_id):
        self.id_composer.exited(thread_asynctask_id)
        del self.pdb_proxies[thread_asynctask_id]

##__________________________________________________________________||
