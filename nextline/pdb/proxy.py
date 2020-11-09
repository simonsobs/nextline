import queue

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

##__________________________________________________________________||
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

        module_name = frame.f_globals.get('__name__')
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        func_name = frame.f_code.co_name
        # a function name
        # Note: '<module>' for the code produced by compile()

        if not func_name in self.trace.breaks.get(module_name, []):
            return

        # print('{}.{}()'.format(module_name, func_name))

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
