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
class CmdLoop:
    """Communicate with pdb while pdb is running cmdloop()

    An instance is created for each execution of pdb._cmdloop()

    Parameters
    ----------
    pdb : Pdb
        The Pdb instance executing cmdloop()
    queue_in : queue
        The queue connected to stdin in pdb
    queue_out : queue
        The queue connected to stdout in pdb

    """
    def __init__(self, pdb, queue_in, queue_out):
        self.pdb = pdb
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.exited = False
        self.nprompts = 0

    def send_pdb_command(self, command):
        """send a command to pdb
        """
        self.command = command
        self.queue_in.put(command)

    def enter(self):
        self.thread = threading.Thread(target=self._receive_pdb_stdout)
        self.thread.start()

    def exit(self):
        self.exited = True
        self.queue_out.put(None) # end the thread
        self.thread.join()

    def _receive_pdb_stdout(self):
        """receive stdout fomr pdb

        This method runs in its own thread during pdb._cmdloop()
        """
        while out := self._read_uptp_prompt(self.queue_out, self.pdb.prompt):
            self.nprompts += 1
            self.stdout = out

    def _read_uptp_prompt(self, queue, prompt):
        """read the queue up to the prompt
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

class LocalControl:
    '''A local hub of communications to the pdb

    An instance is created for each thread and asyncio task.
    '''

    def __init__(self, thread_task_id, control):
        self.thread_task_id = thread_task_id
        self.control = control

        self.queue_in = queue.Queue() # pdb stdin
        self.queue_out = queue.Queue() # pdb stdout
        self.pdb = PdbWrapper(self, stdin=StreamIn(self.queue_in), stdout=StreamOut(self.queue_out), readrc=False)

    def enter_cmdloop(self):
        self.cmdloop = CmdLoop(self.pdb, self.queue_in, self.queue_out)
        self.cmdloop.enter()
        self.control.enter_cmdloop(self.cmdloop)

    def exit_cmdloop(self):
        self.cmdloop.exit()
        self.control.exit_cmdloop(self.cmdloop)

class Control:
    def __init__(self):
        self.thread_task_ids = set()
        self.local_controls = {}
        self.condition = threading.Condition()
        self.cmdloops = []

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

    def enter_cmdloop(self, cmdloop):
        with self.condition:
            self.cmdloops.append(cmdloop)

    def exit_cmdloop(self, cmdloop):
        with self.condition:
            self.cmdloops.remove(cmdloop)

    def nthreads(self):
        return len({i for i, _ in self.thread_task_ids})

##__________________________________________________________________||
