import threading
import asyncio
import copy
from collections import defaultdict
from functools import partial
from operator import itemgetter
import warnings

from .pdb.proxy import PdbProxy
from .thread_safe_event import ThreadSafeAsyncioEvent

##__________________________________________________________________||
class State:
    """
    """
    def __init__(self):
        self.event = ThreadSafeAsyncioEvent()
        self.event_thread_task_ids = ThreadSafeAsyncioEvent()
        self.condition = threading.Condition()

        self._data = defaultdict(
            partial(
                defaultdict,
                partial(
                    dict,
                    prompting=0,
                    file_name=None,
                    line_no=None,
                    file_lines=[],
                )
            )
        )
        # e.g.,
        # { thread_id : {
        #     task_id: {'prompting': False, ...}
        # }}

        self._prompting_count = 0

    @property
    def data(self):
        with self.condition:
            return copy.deepcopy(self._data)

    def update_started(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({'prompting': 0})
        self.event.set()
        self.event_thread_task_ids.set()

    def update_finishing(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            try:
                del self._data[thread_id][task_id]
            except KeyError:
                warnings.warn("not found: thread_asynctask_id = {}".format(thread_asynctask_id))
            if not self._data[thread_id]:
                try:
                    del self._data[thread_id]
                except KeyError:
                    warnings.warn("not found: thread_asynctask_id = {}".format(thread_asynctask_id))
        self.event.set()
        self.event_thread_task_ids.set()

    def update_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._prompting_count += 1
            self._data[thread_id][task_id]['prompting'] = self._prompting_count
        self.event.set()

    def update_not_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['prompting'] = 0
        self.event.set()

    def update_file_name_line_no(self, thread_asynctask_id, file_name, line_no):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({'file_name': file_name, 'line_no': line_no})
        # self.event.set()

    def update_file_lines(self, thread_asynctask_id, file_lines):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['file_lines'] = file_lines
        # self.event.set()

    @property
    def thread_task_ids(self):
        '''list of thread_asynctask_ids

        '''
        with self.condition:
            ret = [
                (thid, taid)
                for thid, thda in self._data.items()
                for taid, tada in thda.items()
            ]
        return ret

    @property
    def prompting(self):
        '''list of thread_asynctask_id for which pdb is prompting in the order of started prompting

        '''
        with self.condition:
            ret = [
                (thid, taid, tada['prompting'])
                for thid, thda in self._data.items()
                for taid, tada in thda.items() if tada['prompting'] > 0
            ]
            # (thread_id, task_id, prompting)
        ret = sorted(ret, key=itemgetter(2)) # sort by prompting
        ret = [e[0:2] for e in ret] # (thread_id, task_id)
        return ret

    @property
    def nthreads(self):
        '''number of running threads
        '''
        with self.condition:
            running_thread_ids = [
                thid for thid, thda in self._data.items()
            ]
        return len(running_thread_ids)

class PdbCIRegistry:
    """Hold the list of active pdb command interfaces
    """
    def __init__(self):
        self.pdb_cis = []
        self._dict = {}
        self.condition = threading.Condition()

    def add(self, thread_asynctask_id, pdb_ci):
        with self.condition:
            self._dict[thread_asynctask_id] = pdb_ci
            self.pdb_cis.append(pdb_ci)

    def remove(self, thread_asynctask_id):
        with self.condition:
            pdb_ci = self._dict.pop(thread_asynctask_id)
            self.pdb_cis.remove(pdb_ci)

    def get_ci(self, thread_asynctask_id):
        with self.condition:
            return self._dict.get(thread_asynctask_id, None)

class Trace:
    """The main trace function

    An instance of this class, which is callable, should be set as the
    trace function by sys.settrace() and threading.settrace().

    """
    def __init__(self, state, breaks=None, statement=None):

        if statement is None:
            statement = ""

        if breaks is None:
            breaks = {}

        # public
        self.state = state
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
                    trace=self,
                    thread_asynctask_id=thread_asynctask_id,
                    breaks=self.breaks,
                    state=self.state,
                    ci_registry=self.pdb_ci_registry,
                    statement=self.statement
                )
                self.pdb_proxies[thread_asynctask_id] = pdb_proxy

        return pdb_proxy.trace_func(frame, event, arg)

    def returning(self, thread_asynctask_id):
        with self.condition:
            del self.pdb_proxies[thread_asynctask_id]

##__________________________________________________________________||
def compose_thread_asynctask_id():
    """Return the pair of the current thread ID and async task ID

    The IDs are unique among exiting threads and async tasks. However,
    they might be reused after threads or async tasks exit.


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
