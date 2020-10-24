import asyncio
import janus

##__________________________________________________________________||
class LocalControl:
    def __init__(self, local_queues):
        self.q_in, self.q_out = local_queues
    async def run(self):
        while True:
            m = await self.q_out.async_q.get()
            if m is None: # end
                break
            await self.q_in.async_q.put(m)

class Control:
    def __init__(self, global_queue, local_queue_dict, condition):
        self.global_queue = global_queue
        self.local_queue_dict = local_queue_dict # shared
        self.condition = condition # used to lock for local_queue_dict
        self.local_controls = {}

    async def run(self):
        await self._start_local_controls()
        await self._end()

    async def _start_local_controls(self):
        while True:
            thread_task_id = await self.global_queue.async_q.get()
            if thread_task_id is None: # end
                break
            if thread_task_id not in self.local_controls:
                local_control = self._create_local_control(thread_task_id)
                self.local_controls[thread_task_id] = asyncio.create_task(local_control.run())

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
        await asyncio.gather(*self.local_controls.values())
        self.global_queue.close()
        await self.global_queue.wait_closed()

##__________________________________________________________________||

##__________________________________________________________________||
async def print_upto_prompt(queue):
    while True:
        m = await queue.get()
        if m is None:
            return True # pdb ended
        print(m, end='')
        if '(Pdb)' in m:
            break

async def control_pdb(commands, queue_in, queue_out):
    for command in commands:
        if await print_upto_prompt(queue_out):
            break
        print(command)
        await queue_in.put(command)

##__________________________________________________________________||
