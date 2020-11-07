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
class PdbProxyInCmdLoop:
    """Send commands to pdb while pdb is in the command loop

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

    def entering_cmdloop(self):
        """notify the pdb is entering the command loop

        This class starts waiting for the output of the pdb
        """
        self.thread = threading.Thread(target=self._receive_pdb_stdout)
        self.thread.start()

    def exited_cmdloop(self):
        """notify the pdb has exited from the command loop

        This class stops waiting for the output of the pdb
        """
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

class PdbCmdLoopRegistry:
    '''Be notified when the pdb enters and exits from the command loop

    An instance is created for each thread and asyncio task. When the
    pdb enters the command loop, the instance starts a proxy, which
    receives the output of the pdb and sends commands to the pdb. When
    the pdb exits from the command loop, the instance stops the proxy.

    '''

    def __init__(self, thread_task_id, control):
        self.thread_task_id = thread_task_id
        self.control = control

        self.queue_in = queue.Queue() # pdb stdin
        self.queue_out = queue.Queue() # pdb stdout
        self.pdb = PdbWrapper(self, stdin=StreamIn(self.queue_in), stdout=StreamOut(self.queue_out), readrc=False)

    def enter_cmdloop(self):
        self.pdb_proxy = PdbProxyInCmdLoop(self.pdb, self.queue_in, self.queue_out)
        self.pdb_proxy.entering_cmdloop()
        self.control.enter_cmdloop(self.pdb_proxy)

    def exit_cmdloop(self):
        self.pdb_proxy.exited_cmdloop()
        self.control.exit_cmdloop(self.pdb_proxy)

class ThreadAsyncTaskRegistry:
    '''Be notified when the trace function is called in a new thread or async task

    '''
    def __init__(self):
        self.thread_task_ids = set()
        self.pdb_cmdloop_registries = {}
        self.condition = threading.Condition()
        self.pdb_proxys = []

    def end(self):
        pass

    def local_control(self, thread_task_id):
        with self.condition:
            ret = self.pdb_cmdloop_registries.get(thread_task_id)
            if ret:
                return ret
            ret = PdbCmdLoopRegistry(thread_task_id=thread_task_id, control=self)
            self.thread_task_ids.add(thread_task_id)
            self.pdb_cmdloop_registries[thread_task_id] = ret
            return ret

    def enter_cmdloop(self, cmdloop):
        with self.condition:
            self.pdb_proxys.append(cmdloop)

    def exit_cmdloop(self, cmdloop):
        with self.condition:
            self.pdb_proxys.remove(cmdloop)

    def nthreads(self):
        return len({i for i, _ in self.thread_task_ids})

##__________________________________________________________________||
