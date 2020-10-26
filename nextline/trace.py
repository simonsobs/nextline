import threading
import asyncio

##__________________________________________________________________||
class LocalTrace:
    def __init__(self, local_queues, thread_task_id):
        self.q_in, self.q_out = local_queues
        self.thread_task_id = thread_task_id

    def __call__(self, frame, event, arg):
        # self.q_out.sync_q.put(self.thread_task_id)
        # print(self.q_in.sync_q.get())

        message = {'called': {'frame': frame, 'event': event, 'arg': arg}}
        self.q_out.sync_q.put(message)
        while True:
            cmd = self.q_in.sync_q.get()
            if cmd == 'next':
                return self
            else:
                message = {'message': 'unrecognized command {!r}'.format(cmd)}
                self.q_out.sync_q.put(message)
        return self

class Trace:
    def __init__(self, global_queue, local_queue_dict, condition, breaks):
        self.global_queue = global_queue
        self.local_queue_dict = local_queue_dict
        self.condition = condition
        self.breaks = breaks

    def __call__(self, frame, event, arg):

        module_name = frame.f_globals.get('__name__')
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        func_name = frame.f_code.co_name
        # '<module>' for the code produced by compile()

        if not func_name in self.breaks.get(module_name, []):
            return

        # print('Event: {}'.format(event))
        # print('Module name: {!r}'.format(module_name))
        # print('File name: {}'.format(frame.f_code.co_filename))
        # print('Line number: {}'.format(frame.f_lineno))
        # print('Function name: {!r}'.format(func_name))

        print('{}.{}()'.format(module_name, func_name))

        thread_task_id = create_thread_task_id()
        print(*thread_task_id)

        local_queues = self._find_local_queues(thread_task_id)
        if not local_queues:
            warnings.warn('could not find queues for {!r}'.format(thread_task_id))
            return

        trace_local = LocalTrace(local_queues, thread_task_id)

        return trace_local(frame, event, arg)

    def _find_local_queues(self, thread_task_id):

        with self.condition:
            ret = self.local_queue_dict.get(thread_task_id)

        if ret is None:
            q = self.global_queue.sync_q
            try:
                q.put(thread_task_id)
            except RuntimeError:
                # this happens, for example, in concurrent/futures/thread.py
                warnings.warn("could not put an item in the queue: {!r}".format(q))
                return None

            # TODO: Add timeout
            while not ret:
                with self.condition:
                    ret = self.local_queue_dict.get(thread_task_id)

        return ret

##__________________________________________________________________||
def create_thread_task_id():

    thread_id = threading.get_ident()

    task_id = None
    try:
        task_id = id(asyncio.current_task())
    except RuntimeError:
        # no running event loop
        pass

    return (thread_id, task_id)

##__________________________________________________________________||
