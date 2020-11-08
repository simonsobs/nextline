import threading
import queue
import warnings
from pdb import Pdb

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
class PdbWrapper(Pdb):
    # created for each asyncio task

    def __init__(self, local_control, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_control = local_control

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)

        self.super_trace_dispatch = super().trace_dispatch

    def trace_dispatch_wrapper(self, frame, event, arg):
        if self.super_trace_dispatch:
            self.super_trace_dispatch = self.super_trace_dispatch(frame, event, arg)
        return self.trace_dispatch_wrapper

    def _cmdloop(self):
        self.local_control.enter_cmdloop()
        super()._cmdloop()
        self.local_control.exit_cmdloop()


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

    def __init__(self, thread_asynctask_id, control):
        self.thread_asynctask_id = thread_asynctask_id
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

##__________________________________________________________________||
