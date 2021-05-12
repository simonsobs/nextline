import threading
import asyncio
from collections import defaultdict
from functools import partial
from operator import itemgetter
import warnings

from .utils import QueueDist

##__________________________________________________________________||
class Registry:
    """
    """
    def __init__(self):

        self.loop = asyncio.get_running_loop()

        self.condition = threading.Condition()

        self._data = defaultdict(
            partial(
                defaultdict,
                partial(
                    dict,
                    prompting=0,
                    file_name=None,
                    line_no=None,
                    trace_event=None,
                )
            )
        )
        # e.g.,
        # { thread_id : {
        #     task_id: {'prompting': False, ...}
        # }}

        self._prompting_count = 0

        self.queue_thread_asynctask_ids = QueueDist()
        self.queue_thread_asynctask_ids.put(self.thread_asynctask_ids)
        self.queues_thread_asynctask = {}

    async def close(self):
        await self.queue_thread_asynctask_ids.close()
        for q in self.queues_thread_asynctask.values():
            await q.close()
        self.queues_thread_asynctask.clear()

    def update_started(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({'prompting': 0})

        fut = asyncio.run_coroutine_threadsafe(self._update_started(thread_asynctask_id), self.loop)
        fut.result() # to wait and get the return value

    async def _update_started(self, thread_asynctask_id):
        with self.condition:
            if thread_asynctask_id in self.queues_thread_asynctask:
                return
            self.queues_thread_asynctask[thread_asynctask_id] = QueueDist()
            self.queue_thread_asynctask_ids.put(self.thread_asynctask_ids)

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

        fut = asyncio.run_coroutine_threadsafe(self._update_finishing(thread_asynctask_id), self.loop)
        fut.result() # to wait and get the return value

    async def _update_finishing(self, thread_asynctask_id):
        with self.condition:
            self.queue_thread_asynctask_ids.put(self.thread_asynctask_ids)
            q = self.queues_thread_asynctask.pop(thread_asynctask_id, None)
            if q:
                await q.close()

    def update_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._prompting_count += 1
            self._data[thread_id][task_id]['prompting'] = self._prompting_count
        self.publish_thread_asynctask_state(thread_asynctask_id)

    def update_not_prompting(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id]['prompting'] = 0
        self.publish_thread_asynctask_state(thread_asynctask_id)

    def publish_thread_asynctask_state(self, thread_asynctask_id):
        thread_id, task_id = thread_asynctask_id
        th = self._data[thread_id]
        if th:
            ta = th[task_id]
            if ta:
                self.queues_thread_asynctask[thread_asynctask_id].put(ta.copy())

    def update_file_name_line_no(self, thread_asynctask_id, file_name, line_no, trace_event):
        thread_id, task_id = thread_asynctask_id
        with self.condition:
            self._data[thread_id][task_id].update({
                'file_name': file_name,
                'line_no': line_no,
                'trace_event': trace_event
            })

    async def subscribe_thread_asynctask_ids(self):
        async for y in self.queue_thread_asynctask_ids.subscribe():
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        async for y in self.queues_thread_asynctask[thread_asynctask_id].subscribe():
            yield y

    @property
    def thread_asynctask_ids(self):
        '''list of thread_asynctask_ids

        '''
        with self.condition:
            ret = [
                (thid, taid)
                for thid, thda in self._data.items()
                for taid, tada in thda.items()
            ]
        return ret

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

##__________________________________________________________________||
