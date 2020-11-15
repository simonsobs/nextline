import queue
import asyncio
import linecache

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

##__________________________________________________________________||
class PdbProxy:
    '''A proxy of Pdb

    An instance of this class is created for each thread or async task.

    '''

    def __init__(self, thread_asynctask_id, breaks, state, ci_registry, statement):
        self.thread_asynctask_id = thread_asynctask_id
        self.breaks = breaks
        self.state = state
        self.ci_registry = ci_registry
        self.statement = statement

        self.q_stdin = queue.Queue()
        self.q_stdout = queue.Queue()

        self.pdb = CustomizedPdb(
            proxy=self,
            stdin=StreamIn(self.q_stdin),
            stdout=StreamOut(self.q_stdout),
            readrc=False)

        self._trace_func_all = self.trace_func_all
        self._pdb_trace_dispatch = self.pdb.trace_dispatch

        self._first = True

    def trace_func(self, frame, event, arg):
        """The main trace function

        This method will be called by the instance of Trace.
        """
        if self._first:
            self._first = False
            return self.trace_func_outermost(frame, event, arg)
        return self.trace_func_all(frame, event, arg)

    def trace_func_outermost(self, frame, event, arg):
        """The trace function of the outermost scope in the thread or async task

        This method is used as a trace function of the outermost scope
        of the thread or async task. It is used to detect the end of
        the thread or async task.

        """
        if event == 'call':
            self.state.update_started(self.thread_asynctask_id)
        if self._trace_func_all:
            self._trace_func_all = self._trace_func_all(frame, event, arg)
        if event == 'return':
            if not isinstance(arg, asyncio.tasks._GatheringFuture):
                self.state.update_finishing(self.thread_asynctask_id)
        return self.trace_func_outermost

    def trace_func_all(self, frame, event, arg):
        """The trace function that calls the trace function of pdb

        """

        module_name = frame.f_globals.get('__name__')
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        func_name = frame.f_code.co_name
        # a function name
        # Note: '<module>' for the code produced by compile()

        if not func_name in self.breaks.get(module_name, []):
            return

        # print('{}.{}()'.format(module_name, func_name))

        file_name = self.pdb.canonic(frame.f_code.co_filename)
        line_no = frame.f_lineno
        # print('{}:{}'.format(file_name, line_no))
        self.state.update_file_name_line_no(self.thread_asynctask_id, file_name, line_no)

        if file_name == '<string>':
            file_lines = self.statement.split('\n')
        else:
            file_lines = [l.rstrip() for l in linecache.getlines(file_name, frame.f_globals)]
        self.state.update_file_lines(self.thread_asynctask_id, file_lines)

        if self._pdb_trace_dispatch:
            self._pdb_trace_dispatch = self._pdb_trace_dispatch(frame, event, arg)
        return self.trace_func_all

    def entering_cmdloop(self):
        """called by the customized pdb before it is entering the command loop
        """
        self.pdb_ci = PdbCommandInterface(self.pdb, self.q_stdin, self.q_stdout)
        self.pdb_ci.start()
        self.state.update_prompting(self.thread_asynctask_id)
        self.ci_registry.add(self.thread_asynctask_id, self.pdb_ci)

    def exited_cmdloop(self):
        """called by the customized pdb after it has exited from the command loop
        """
        self.ci_registry.remove(self.thread_asynctask_id)
        self.state.update_not_prompting(self.thread_asynctask_id)
        self.pdb_ci.end()

##__________________________________________________________________||
