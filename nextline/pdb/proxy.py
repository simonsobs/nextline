import queue
import asyncio

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

##__________________________________________________________________||
class PdbProxy:
    '''A proxy of Pdb

    An instance of this class is created for each thread or async task.

    '''

    def __init__(self, thread_asynctask_id, trace, state):
        self.thread_asynctask_id = thread_asynctask_id
        self.trace = trace
        self.state = state

        self.q_stdin = queue.Queue()
        self.q_stdout = queue.Queue()

        self.pdb = CustomizedPdb(
            proxy=self,
            stdin=StreamIn(self.q_stdin),
            stdout=StreamOut(self.q_stdout),
            readrc=False)

        self._trace_func = self.trace_func
        self._pdb_trace_dispatch = self.pdb.trace_dispatch

    def trace_func_init(self, frame, event, arg):
        """A trace function of the outermost scope in the thread or async task

        This method is used as a trace function of the outermost scope
        of the thread or async task. It is used to detect the end of
        the thread or async task.

        """
        if event == 'call':
            self.state.start_thread_asynctask(self.thread_asynctask_id)
        if self._trace_func:
            self._trace_func = self._trace_func(frame, event, arg)
        if event == 'return':
            if not isinstance(arg, asyncio.tasks._GatheringFuture):
                self.state.end_thread_asynctask(self.thread_asynctask_id)
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

    def entering_cmdloop(self):
        """called by the customized pdb before it is entering the command loop
        """
        self.pdb_ci = PdbCommandInterface(self.pdb, self.q_stdin, self.q_stdout)
        self.pdb_ci.entering_cmdloop()
        self.state.entering_cmdloop(self.pdb_ci)

    def exited_cmdloop(self):
        """called by the customized pdb after it has exited from the command loop
        """
        self.pdb_ci.exited_cmdloop()
        self.state.exited_cmdloop(self.pdb_ci)

##__________________________________________________________________||
