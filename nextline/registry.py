import threading
import asyncio
from collections import defaultdict
from functools import partial
from itertools import count
import linecache
import warnings
from typing import Hashable

from .utils import QueueDist

##__________________________________________________________________||
class Engine:
    """will be renamed Registry

    Registry now will be renamed something else
    """
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self._data = {}
        self._queue = {}
        self._aws = []

    async def close(self):
        # print('close()', self._aws)
        if self._aws:
            await asyncio.gather(*self._aws)
        # print('close()', self._queue)
        while self._queue:
            _, q = self._queue.popitem()
            await q.close()
        # print('close()', self._queue)
        self._data.clear()

    def open_register(self, key: Hashable):
        if key in self._data:
           raise Exception(f'register key already exists {key!r}')
        self._data[key] = None

        coro = self._create_queue(key)
        task = self._run_coroutine(coro)
        if task:
            self._aws.append(task)

    def close_register(self, key: Hashable):
        try:
            del self._data[key]
        except KeyError:
            warnings.warn(f'key not found: {key}')
        coro = self._close_queue(key)
        task = self._run_coroutine(coro)
        if task:
            self._aws.append(task)

    async def _create_queue(self, key):
        """Create a queue

        This method needs to run in self.loop.
        """
        if key in self._queue:
            return
        queue = QueueDist()
        self._queue[key] = queue

    async def _close_queue(self, key):
        """Close a queue

        This method needs to run in self.loop.
        """
        queue = self._queue.pop(key, None)
        if queue:
            await queue.close()

    def register(self, key, item):
        # print(f'register({key!r}, {item!r})')
        if key not in self._data:
            raise Exception(f'register key does not exist {key!r}')

        self._data[key] = item

        coro = self._distribute(key, item)
        task = self._run_coroutine(coro)
        if task:
            self._aws.append(task)

    async def _distribute(self, key, item):
        # print(f'_distribute({key!r}, {item!r})')
        self._queue[key].put(item)

    def get(self, key):
        return self._data[key]

    async def subscribe(self, key):
        queue = self._queue.get(key)
        if not queue:
            await self._create_queue(key)
            queue = self._queue.get(key)
        async for y in queue.subscribe():
            yield y

    def _run_coroutine(self, coro):
        """Run a coroutine in the loop.

        Return a task if in the loop. If not in the loop, schedule to
        run in the loop and wait until it exits.

        """

        if self._is_the_same_running_loop():
            return asyncio.create_task(coro)

        # not in the loop, i.e., in another thread

        if self.loop.is_closed():
            # The loop in the main thread is closed.
            warnings.warn(f'The loop is closed: {self.loop}')
            return

        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        fut.result()

    def _is_the_same_running_loop(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        return self.loop is loop

class Registry:
    """
    """
    def __init__(self):
        self.engine = Engine()

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

        self.engine.open_register('thread_task_ids')
        self.engine.register('thread_task_ids', self.thread_task_ids)

        self.engine.open_register('statement')
        self.engine.open_register('state_name')
        self.engine.open_register('script_file_name')

    def register_state_name(self, state_name):
        self.engine.register('state_name', state_name)

    async def subscribe_state_name(self):
        agen = self.engine.subscribe('state_name')
        async for y in agen:
            yield y

    def register_statement(self, statement):
        self.engine.register('statement', statement)

    def get_statement(self):
        return self.engine.get('statement')

    def register_script_file_name(self, script_file_name):
        self.engine.register('script_file_name', script_file_name)

    def get_script_file_name(self):
        return self.engine.get('script_file_name')

    def get_source(self, file_name=None):
        if not file_name or file_name == self.engine.get('script_file_name'):
            return self.engine.get('statement').split('\n')
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
        await self.engine.close()


    def register_thread_task_id(self, thread_task_id):
        with self.condition:
            self._data[thread_task_id].update({'prompting': 0})

        try:
            self.engine.open_register(thread_task_id)
        except:
            # The same thread_task_id can occur multiple times
            # because, in trace_func_outermost(),
            # self.registry.register_thread_task_id() can be called
            # multiple times for the same self.thread_asynctask_id for
            # ayncio tasks
            pass
        self.engine.register('thread_task_ids', self.thread_task_ids)

    def deregister_thread_task_id(self, thread_task_id):
        with self.condition:
            try:
                del self._data[thread_task_id]
            except KeyError:
                warnings.warn("not found: thread_task_id = {}".format(thread_task_id))

        self.engine.register('thread_task_ids', self.thread_task_ids)
        self.engine.close_register(thread_task_id)

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
            self.engine.register(thread_task_id, self._data[thread_task_id].copy())

    async def subscribe_thread_task_ids(self):
        agen = self.engine.subscribe('thread_task_ids')
        async for y in agen:
            yield y

    async def subscribe_thread_task_state(self, thread_task_id):
        async for y in self.engine.subscribe(thread_task_id):
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
