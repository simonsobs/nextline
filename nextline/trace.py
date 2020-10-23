import threading


##__________________________________________________________________||
class LocalTrace:
    def __init__(self, jqueue_in, jqueue_out, thread_id, task_id):
        self.jqueue_in = jqueue_in
        self.jqueue_out = jqueue_out
        self.thread_id = thread_id
        self.task_id = task_id

    def __call__(self, frame, event, arg):
        self.jqueue_out.sync_q.put((self.thread_id, self.task_id))
        print(self.jqueue_in.sync_q.get())
        self.jqueue_out.sync_q.put((frame, event, arg))
        print(self.jqueue_in.sync_q.get())
        return self

class Trace:
    def __init__(self, jqueue, local_queue_dict, condition, breaks):
        self.jqueue = jqueue
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

        thread_id = threading.get_ident()

        task_id = None
        try:
            task_id = id(asyncio.current_task())
        except:
            pass

        local_queues = self._find_local_queues(thread_id, task_id)
        if not local_queues:
            warnings.warn('could not find queues for {!r}'.format((thread_id, task_id)))
            return

        trace_local = LocalTrace(*local_queues, thread_id, task_id)

        trace_local(frame, event, arg)
        return trace_local

    def _find_local_queues(self, thread_id, task_id):

        key = (thread_id, task_id)

        with self.condition:
            ret = self.local_queue_dict.get(key)

        if ret is None:
            q = self.jqueue.sync_q
            try:
                q.put(key)
            except RuntimeError:
                # this happens, for example, in concurrent/futures/thread.py
                warnings.warn("could not put an item in the queue: {!r}".format(q))
                return None

            while not ret:
                with self.condition:
                    ret = self.local_queue_dict.get(key)

        return ret

##__________________________________________________________________||
