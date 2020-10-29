import threading
import queue
import warnings

##__________________________________________________________________||
class LocalControl:
    def __init__(self, thread_task_id, control):
        self.thread_task_id = thread_task_id
        self.control = control
        self.queue = queue.Queue()

    def __call__(self, message):
        self.message = message
        self.control.prompt(self)
        m = self.queue.get()
        self.control.received(self)
        return m

    def do(self, command):
        self.queue.put(command)

class Control:
    def __init__(self):
        self.thread_task_ids = set()
        self.local_controls = {}
        self.condition = threading.Condition()
        self.waiting = {}

    def local_control(self, thread_task_id):
        with self.condition:
            ret = self.local_controls.get(thread_task_id)
            if ret:
                return ret
            ret = LocalControl(thread_task_id=thread_task_id, control=self)
            self.thread_task_ids.add(thread_task_id)
            self.local_controls[thread_task_id] = ret
            return ret

    def prompt(self, local_control):
        with self.condition:
            self.waiting[local_control.thread_task_id] = local_control
        # print(local_control.message)
        # local_control.do('next')

    def received(self, local_control):
        thread_task_id = local_control.thread_task_id
        try:
            with self.condition:
                self.waiting.pop(thread_task_id)
        except KeyError:
            warnings.warn("the command for {} wasn't waited for.".format(thread_task_id))

    def nthreads(self):
        return len({i for i, _ in self.thread_task_ids})

    def send_command(self, thread_task_ids, command):
        local_control = self.local_controls.get(thread_task_ids)
        if local_control is None:
            warnings.warn("cannot find a local control for {}.".format(thread_task_id))
            return
        local_control.do(command)

##__________________________________________________________________||
