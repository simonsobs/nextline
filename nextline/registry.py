import threading
import asyncio
from collections import defaultdict
from functools import partial
from itertools import count
import linecache
import warnings

from .utils import QueueDist

##__________________________________________________________________||
class Engine:
    """will be renamed Registry

    Registry now will be renamed something else
    """
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self._data = {}

    async def close(self):
        for f in self._data.values():
            await f['queue'].close()

    def add_field(self, key):
        # need to check the loop
        if key in self._data:
            raise Exception(f'key already exist {key!r}')
        self._data[key] = {'entry': None, 'queue': QueueDist()}

    def register(self, key, item):
        self._data[key]['entry'] = item
        self._data[key]['queue'].put(item)

    async def subscribe(self, key):
        agen = self._data[key]['queue'].subscribe()
        async for y in agen:
            yield y

class Registry:
    """
    """
    def __init__(self):

        self.loop = asyncio.get_running_loop()

        self.condition = threading.Condition()

        # key thread_task_id
        self._data = defaultdict(
            partial(
                dict,
                prompting=0,
                file_name=None,
                line_no=None,
                trace_event=None,
            )
        )

        self.prompting_counter = count().__next__
        self.prompting_counter() # consume 0

        self.queue_thread_task_ids = QueueDist()
        self.queue_thread_task_ids.put(self.thread_task_ids)
        self.queues_thread_task_state = {}

        self.statement = None

        self.state_name = None
        self.queue_state_name = QueueDist()

    def register_state_name(self, state_name):
        self.state_name = state_name
        self.queue_state_name.put(state_name)

    async def subscribe_state_name(self):
        agen = self.queue_state_name.subscribe()
        async for y in agen:
            yield y

    def register_statement(self, statement):
        self.statement = statement

    def get_statement(self):
        return self.statement

    def register_script_file_name(self, script_file_name):
        self.script_file_name = script_file_name

    def get_script_file_name(self):
        return self.script_file_name

    def get_source(self, file_name=None):
        if not file_name or file_name == self.script_file_name:
            return self.statement.split('\n')
        return [l.rstrip() for l in linecache.getlines(file_name)]

    def get_source_line(self, line_no, file_name=None):
        '''
        based on linecache.getline()
        https://github.com/python/cpython/blob/v3.9.5/Lib/linecache.py#L26
        '''
        lines = self.get_source(file_name)
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ''

    async def close(self):
        await self.queue_thread_task_ids.close()
        for q in self.queues_thread_task_state.values():
            await q.close()
        self.queues_thread_task_state.clear()
        await self.queue_state_name.close()

    def register_thread_task_id(self, thread_task_id):
        with self.condition:
            self._data[thread_task_id].update({'prompting': 0})

        fut = asyncio.run_coroutine_threadsafe(self._register_thread_task_id(thread_task_id), self.loop)
        fut.result() # to wait and get the return value

    async def _register_thread_task_id(self, thread_task_id):
        with self.condition:
            if thread_task_id in self.queues_thread_task_state:
                return
            self.queues_thread_task_state[thread_task_id] = QueueDist()
            self.queue_thread_task_ids.put(self.thread_task_ids)

    def deregister_thread_task_id(self, thread_task_id):
        with self.condition:
            try:
                del self._data[thread_task_id]
            except KeyError:
                warnings.warn("not found: thread_task_id = {}".format(thread_task_id))

        fut = asyncio.run_coroutine_threadsafe(self._deregister_thread_task_id(thread_task_id), self.loop)
        fut.result() # to wait and get the return value

    async def _deregister_thread_task_id(self, thread_task_id):
        with self.condition:
            self.queue_thread_task_ids.put(self.thread_task_ids)
            q = self.queues_thread_task_state.pop(thread_task_id, None)
            if q:
                await q.close()

    def register_thread_task_state(self, thread_task_id, file_name, line_no, trace_event):
        with self.condition:
            self._data[thread_task_id].update({
                'file_name': file_name,
                'line_no': line_no,
                'trace_event': trace_event
            })

    def register_prompting(self, thread_task_id):
        with self.condition:
            self._data[thread_task_id]['prompting'] = self.prompting_counter()
        self.publish_thread_task_state(thread_task_id)

    def deregister_prompting(self, thread_task_id):
        with self.condition:
            self._data[thread_task_id]['prompting'] = 0
        self.publish_thread_task_state(thread_task_id)

    def publish_thread_task_state(self, thread_task_id):
        if thread_task_id in self._data:
            self.queues_thread_task_state[thread_task_id].put(self._data[thread_task_id].copy())

    async def subscribe_thread_task_ids(self):
        async for y in self.queue_thread_task_ids.subscribe():
            yield y

    async def subscribe_thread_task_state(self, thread_task_id):
        async for y in self.queues_thread_task_state[thread_task_id].subscribe():
            yield y

    @property
    def thread_task_ids(self):
        '''list of thread_task_ids

        '''
        with self.condition:
            return list(self._data.keys())

class PdbCIRegistry:
    """Hold the list of active pdb command interfaces
    """
    def __init__(self):
        self.pdb_cis = []
        self._dict = {}
        self.condition = threading.Condition()

    def add(self, thread_task_id, pdb_ci):
        with self.condition:
            self._dict[thread_task_id] = pdb_ci
            self.pdb_cis.append(pdb_ci)

    def remove(self, thread_task_id):
        with self.condition:
            pdb_ci = self._dict.pop(thread_task_id)
            self.pdb_cis.remove(pdb_ci)

    def get_ci(self, thread_task_id):
        with self.condition:
            return self._dict.get(thread_task_id, None)

##__________________________________________________________________||
