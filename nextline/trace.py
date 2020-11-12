import threading
import asyncio

from .pdb.proxy import PdbProxy

##__________________________________________________________________||
class State:
    """
    """
    def __init__(self, condition):
        self.condition = condition
        self.pdb_cis = []
        self.thread_asynctask_ids = set()

    def start_thread_asynctask(self, thread_asynctask_id):
        with self.condition:
            self.thread_asynctask_ids.add(thread_asynctask_id)

    def entering_cmdloop(self, pdb_ci):
        with self.condition:
            self.pdb_cis.append(pdb_ci)

    def exited_cmdloop(self, pdb_ci):
        with self.condition:
            self.pdb_cis.remove(pdb_ci)

    def nthreads(self):
        with self.condition:
            return len({i for i, _ in self.thread_asynctask_ids})

class Trace:
    """The main trace function

    An instance of this class is callable and should be set as the trace
    function by sys.settrace() and threading.settrace().

    """
    def __init__(self, statement=None, breaks=None):

        if statement is None:
            statement = ""

        if breaks is None:
            breaks = {}

        self.statement = statement
        self.breaks = breaks
        self.condition = threading.Condition()
        self.pdb_proxies = {}
        self.state = State(self.condition)

    def __call__(self, frame, event, arg):
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        thread_asynctask_id = compose_thread_asynctask_id()
        # print(*thread_asynctask_id)

        with self.condition:
            if pdb_proxy := self.pdb_proxies.get(thread_asynctask_id):
                return pdb_proxy.trace_func(frame, event, arg)

        pdb_proxy = PdbProxy(thread_asynctask_id=thread_asynctask_id, trace=self, state=self.state)
        self.pdb_proxies[thread_asynctask_id] = pdb_proxy
        return pdb_proxy.trace_func_init(frame, event, arg)

##__________________________________________________________________||
def compose_thread_asynctask_id():
    """Return the pair of the current thread ID and async task ID

    Returns
    -------
    tuple
        The pair of the current thread ID and async task ID. If not in an
        async task, the async task ID will be None.

    """

    thread_id = threading.get_ident()

    asynctask_id = None
    try:
        asynctask_id = id(asyncio.current_task())
    except RuntimeError:
        # no running event loop
        pass

    return (thread_id, asynctask_id)

##__________________________________________________________________||
