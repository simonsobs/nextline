import threading
import asyncio
import copy
from collections import defaultdict
from functools import partial
from operator import itemgetter
import warnings

from .pdb.proxy import PdbProxy

##__________________________________________________________________||
class State:
    """
    """
    def __init__(self):
        self.condition = threading.Condition()

        self._data = defaultdict(
            partial(
                defaultdict,
                partial(
                    dict,
                    finished=False,
                    prompting=0,
                    file_name=None,
                    line_no=None,
                    file_lines=[],
                )
            )
        )
        # e.g.,
        # { thread_id : {
        #     task_id: {'finished': False, 'prompting': False, ...}
        # }}

        self._prompting_count = 0

    @property
    def data(self):
        return copy.deepcopy(self._data)

    def update_started(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({'finished': False, 'prompting': 0})

    def update_finishing(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            if self._data[thread_id][task_id]['finished']:
                warnings.warn("already finished: thread_asynctask_id = {}".format(thread_asynctask_id))
            self._data[thread_id][task_id]['finished'] = True

    def update_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._prompting_count += 1
            self._data[thread_id][task_id]['prompting'] = self._prompting_count

    def update_not_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['prompting'] = 0

    def update_file_name_line_no(self, thread_asynctask_id, file_name, line_no):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({'file_name': file_name, 'line_no': line_no})

    def update_file_lines(self, thread_asynctask_id, file_lines):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['file_lines'][:] = file_lines

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
                if any([not tada['finished'] for tada in thda.values()])
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
