import asyncio
import janus

##__________________________________________________________________||
class LocalControl:
    def __init__(self, local_queues):
        self.q_to_local_trace, self.q_from_local_trace = local_queues
    async def run(self):
        while True:
            m = await self.q_from_local_trace.async_q.get()
            if m is None: # end
                break
            await self.q_to_local_trace.async_q.put('next')

class Control:
    def __init__(self, queue_from_trace, local_queue_dict, condition):
        self.queue_from_trace = queue_from_trace
        self.local_queue_dict = local_queue_dict # shared
        self.condition = condition # used to lock for local_queue_dict
        self.thread_task_ids = set()
        self.local_control_tasks = set()

    async def run(self):
        await self._start_local_controls()
        await self._end()

    async def _start_local_controls(self):
        while True:
            thread_task_id = await self.queue_from_trace.async_q.get()
            # queue_task = asyncio.create_task(self.queue_from_trace.async_q.get())
            # done, pending = await asyncio.wait( {queue_task} | self.local_control_tasks, return_when=asyncio.FIRST_COMPLETED)
            # if queue_task in done:
            #     thread_task_id = queue_task.result()
            # # TODO: Add else-clause
            if thread_task_id is None: # end
                break
            if thread_task_id not in self.thread_task_ids:
                local_control = self._create_local_control(thread_task_id)
                self.thread_task_ids.add(thread_task_id)
                task = asyncio.create_task(local_control.run())
                self.local_control_tasks.add(task)

    def _create_local_control(self, thread_task_id):
        with self.condition:
            local_queues = self.local_queue_dict.get(thread_task_id)
            if local_queues:
                warnings.warn('local queues for {} already exist'.format(thread_task_id))
            else:
                local_queues = (janus.Queue(), janus.Queue())
                self.local_queue_dict[thread_task_id] = local_queues
        return LocalControl(local_queues)

    async def _end(self):
        for _, q_out in self.local_queue_dict.values():
            q_out.sync_q.put(None)
        await asyncio.gather(*self.local_control_tasks)
        self.queue_from_trace.close()
        await self.queue_from_trace.wait_closed()

##__________________________________________________________________||
