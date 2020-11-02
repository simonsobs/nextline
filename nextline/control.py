import threading
import queue
import warnings
import pdb

##__________________________________________________________________||
class StreamOut:
    def __init__(self, queue):
        self.queue = queue
    def write(self, s):
        self.queue.put(s)
    def flush(self):
        pass

class StreamIn:
    def __init__(self, queue):
        self.queue = queue
    def readline(self):
        return self.queue.get()

##__________________________________________________________________||
class LocalControl:
    def __init__(self, thread_task_id, control):
        self.thread_task_id = thread_task_id
        self.control = control
        self.queue = queue.Queue()

        self.queue_in = queue.Queue()
        self.queue_out = queue.Queue()
        self.pdb = pdb.Pdb(stdin=StreamIn(self.queue_in), stdout=StreamOut(self.queue_out))
        self.pdb.quitting = True
        self.pdb.botframe = None
        self.pdb._set_stopinfo(None, None)

    def __call__(self, message):
        self.message = message
        self.control.prompt(self)
        m = self.queue.get()
        self.control.received(self)
        return m

    def do(self, command):
        self.queue.put(command)

    def start(self):
        self.t = threading.Thread(target=self._listen)
        self.t.start()

    def end(self):
        self.queue_out.put(None)
        self.t.join()

    def _get_until_prompt(self, queue, prompt):
        out = ''
        end = False
        while True:
            m = queue.get()
            if m is None: # end
                end = True
                break
            out += m
            if prompt == m:
                break
        return out, end

    def _listen(self):
        while True:
            out, end = self._get_until_prompt(self.queue_out, self.pdb.prompt)
            if end:
                break
            self.control.prompt(self, out)
            command = self.queue.get()
            self.control.received(self)
            print(command)
            self.queue_in.put(command)

class Control:
    def __init__(self):
        self.thread_task_ids = set()
        self.local_controls = {}
        self.condition = threading.Condition()
        self.waiting = {}
        self.local_pdbs = {}

    def end(self):
        with self.condition:
            for local_control in self.local_controls.values():
                local_control.end()

    def local_control(self, thread_task_id):
        with self.condition:
            ret = self.local_controls.get(thread_task_id)
            if ret:
                return ret
            ret = LocalControl(thread_task_id=thread_task_id, control=self)
            ret.start()
            self.thread_task_ids.add(thread_task_id)
            self.local_controls[thread_task_id] = ret
            return ret

    def prompt(self, local_control, out):
        print(out, end='')
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
