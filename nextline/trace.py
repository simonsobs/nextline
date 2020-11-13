import threading
import asyncio
import copy
from collections import defaultdict
from functools import partial
import warnings

from .pdb.proxy import PdbProxy

##__________________________________________________________________||
class State:
    """
    """
    def __init__(self):
        self.condition = threading.Condition()

        self._data = defaultdict(
            partial(defaultdict, partial(dict, finished=False, prompting=False))
        )
        # e.g.,
        # { thread_id : {
        #     task_id: {'finished': False, 'prompting': False}
        # }}

    @property
    def data(self):
        return copy.deepcopy(self._data)

    def update_started(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({'finished': False, 'prompting': False})

    def update_finishing(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            if self._data[thread_id][task_id]['finished']:
                warnings.warn("already finished: thread_asynctask_id = {}".format(thread_asynctask_id))
            self._data[thread_id][task_id]['finished'] = True

    def update_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['prompting'] = True

    def update_not_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['prompting'] = False

    @property
    def nthreads(self):
        with self.condition:
            running_thread_ids = [
                thid for thid, thda in self._data.items()
                if any([not tada['finished'] for tada in thda.values()])
            ]
        return len(running_thread_ids)

class PdbCIRegistry:
    """Hold the list of active pdb command interfaces
    """
    def __init__(self):
        self.pdb_cis = []
        self.condition = threading.Condition()

    def add(self, pdb_ci):
        with self.condition:
            self.pdb_cis.append(pdb_ci)

    def remove(self, pdb_ci):
        with self.condition:
            self.pdb_cis.remove(pdb_ci)

class Trace:
    """The main trace function

    An instance of this class, which is callable, should be set as the
    trace function by sys.settrace() and threading.settrace().

    """
    def __init__(self, breaks=None, statement=None):

        if statement is None:
            statement = ""

        if breaks is None:
            breaks = {}

        # public
        self.state = State()
        self.pdb_ci_registry = PdbCIRegistry()

        self.pdb_proxies = {}
        self.condition = threading.Condition()

        # these are simply passed to pdb proxies
        self.breaks = breaks
        self.statement = statement

    def __call__(self, frame, event, arg):
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        thread_asynctask_id = compose_thread_asynctask_id()
        # print(*thread_asynctask_id)

        with self.condition:
            if not (pdb_proxy := self.pdb_proxies.get(thread_asynctask_id)):
                pdb_proxy = PdbProxy(
                    thread_asynctask_id=thread_asynctask_id,
                    breaks=self.breaks,
                    state=self.state,
                    ci_registry=self.pdb_ci_registry,
                    statement=self.statement
                )
                self.pdb_proxies[thread_asynctask_id] = pdb_proxy

        return pdb_proxy.trace_func(frame, event, arg)

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
