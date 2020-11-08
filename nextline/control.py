import threading
import queue
from functools import partial
from pdb import Pdb

##__________________________________________________________________||
class PdbCommandInterface:
    """Relay pdb command prompts and commands

    An instance of this class is created for each execution of the pdb
    command loop, pdb._cmdloop().

    Parameters
    ----------
    pdb : Pdb
        The Pdb instance executing _cmdloop()
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

##__________________________________________________________________||
def getlines(func_org, statement, filename, module_globals=None):
    if filename == '<string>':
        return statement.split('\n')
    return func_org(filename, module_globals)

##__________________________________________________________________||
class CustomizedPdb(Pdb):
    """A customized Pdb

    An instance of this class will be created for each thread and async task

    """

    def __init__(self, pdb_proxy, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pdb_proxy = pdb_proxy

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)

    def _cmdloop(self):
        self.pdb_proxy.enter_cmdloop()
        super()._cmdloop()
        self.pdb_proxy.exit_cmdloop()

    def do_list(self, arg):
        statement = self.pdb_proxy.trace.statement
        import linecache
        getlines_org = linecache.getlines
        linecache.getlines = partial(getlines, getlines_org, statement)
        try:
            return super().do_list(arg)
        finally:
            linecache.getlines = getlines_org

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

class PdbProxy:
    '''A proxy of Pdb

    An instance of this class is created for each thread or async task.

    '''

    def __init__(self, thread_asynctask_id, trace):
        self.thread_asynctask_id = thread_asynctask_id
        self.trace = trace

        self.queue_in = queue.Queue() # pdb stdin
        self.queue_out = queue.Queue() # pdb stdout
        stdin = StreamIn(self.queue_in)
        stdout = StreamOut(self.queue_out)
        self.pdb = CustomizedPdb(self, stdin=stdin, stdout=stdout, readrc=False)
        self._pdb_trace_dispatch = self.pdb.trace_dispatch
        self._trace_func = self.trace_func

    def trace_func_init(self, frame, event, arg):
        """A trace function of the outermost scope in the thread or async task

        This method is used as a trace function of the outermost scope
        of the thread or async task. It is used to detect the end of
        the thread or async task.

        """
        if self._trace_func:
            self._trace_func = self._trace_func(frame, event, arg)
        if event == 'return':
            # the end of the thread or async task
            pass
        return self.trace_func_init

    def trace_func(self, frame, event, arg):
        """A trace function

        """
        if self._pdb_trace_dispatch:
            self._pdb_trace_dispatch = self._pdb_trace_dispatch(frame, event, arg)
        return self.trace_func

    def enter_cmdloop(self):
        self.pdb_ci = PdbCommandInterface(self.pdb, self.queue_in, self.queue_out)
        self.pdb_ci.entering_cmdloop()
        self.trace.enter_cmdloop(self.pdb_ci)

    def exit_cmdloop(self):
        self.pdb_ci.exited_cmdloop()
        self.trace.exit_cmdloop(self.pdb_ci)

##__________________________________________________________________||
