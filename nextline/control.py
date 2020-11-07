import threading
import queue
import warnings

from .trace import PdbWrapper

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
    '''A local hub of communications to the pdb

    An instance is created for each asyncio task.
    '''

    def __init__(self, thread_task_id, control):
        self.thread_task_id = thread_task_id
        self.control = control
        self.queue = queue.Queue()

        self.queue_in = queue.Queue() # pdb stdin
        self.queue_out = queue.Queue() # pdb stdout
        self.pdb = PdbWrapper(self, stdin=StreamIn(self.queue_in), stdout=StreamOut(self.queue_out), readrc=False)

    def __call__(self, message):
        self.message = message
        self.control.prompt(self)
        m = self.queue.get()
        self.control.received(self)
        return m

    def do(self, command):
        self.queue.put(command)

    def enter_cmdloop(self):
        self.thread = threading.Thread(target=self._handle_cmds)
        self.thread.start()
        self.cmdloop_info = { "local_control": self, "exit": False, "nprompts": 0 }
        self.control.enter_cmdloop(self.cmdloop_info)

    def exit_cmdloop(self):
        self.cmdloop_info["exit"] = True
        self.control.exit_cmdloop(self.cmdloop_info)
        self.queue_out.put(None)
        self.thread.join()

    def _handle_cmds(self):
        """handle pdb commands

        This method runs in its own thread during pdb._cmdloop()
        """
        while out := self._read_pdb_stdout(self.queue_out, self.pdb.prompt):
            self.cmdloop_info["nprompts"] +=1
            self.cmdloop_info["stdout"] = out
            command = self.queue.get()
            self.cmdloop_info["command"] = command
            self.queue_in.put(command)

    def _read_pdb_stdout(self, queue, prompt):
        """read stdout from pdb up to the prompt
        """
        out = ''
        while True:
            m = queue.get()
            if m is None: # end
                return None
            out += m
            if prompt == m:
                break
        return out

class Control:
    def __init__(self):
        self.thread_task_ids = set()
        self.local_controls = {}
        self.condition = threading.Condition()
        self.cmdloop_info_list = []

    def end(self):
        pass

    def local_control(self, thread_task_id):
        with self.condition:
            ret = self.local_controls.get(thread_task_id)
            if ret:
                return ret
            ret = LocalControl(thread_task_id=thread_task_id, control=self)
            self.thread_task_ids.add(thread_task_id)
            self.local_controls[thread_task_id] = ret
            return ret

    def enter_cmdloop(self, cmdloop_info):
        self.cmdloop_info_list.append(cmdloop_info)

    def exit_cmdloop(self, cmdloop_info):
        self.cmdloop_info_list.remove(cmdloop_info)

    def nthreads(self):
        return len({i for i, _ in self.thread_task_ids})

##__________________________________________________________________||
