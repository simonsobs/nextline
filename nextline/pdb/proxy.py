import queue
import asyncio
import warnings
import linecache
import fnmatch

from .ci import PdbCommandInterface
from .custom import CustomizedPdb
from .stream import StreamIn, StreamOut

##__________________________________________________________________||
MODULES_TO_SKIP = [
    "threading", "queue", "importlib",
    "asyncio.*", "janus", "codec",
    "concurrent.futures.*",
    "selectors", "weakref", "_weakrefset", "socket", "logging", "os",
    "collections.*",
    "importlib.*", "pathlib", "typing", "posixpath", "fnmatch",
    "_pytest.*", "pluggy.*",
    "nextline.pdb.*", "nextline.queuedist", "nextlinegraphql.schema.bindables",
]

##__________________________________________________________________||
class PdbProxy:
    '''A proxy of Pdb

    An instance of this class is created for each thread or async task.

    Parameters
    ----------
    thread_asynctask_id : object
        A thread and async tack ID
    trace : object
        A in stance of Trace
    modules_to_trace: set
        The set of modules to trace. This object is shared by multiple
        instances of this class. Modules in which Pdb commands are
        prompted will be added.
    registry: object
    ci_registry: object
    prompting_counter : callable
    '''

    def __init__(self, thread_asynctask_id, trace, modules_to_trace, registry, ci_registry, prompting_counter):
        self.thread_asynctask_id = thread_asynctask_id
        self.trace = trace
        self.modules_to_trace = modules_to_trace
        self.registry = registry
        self.ci_registry = ci_registry
        self.prompting_counter = prompting_counter
        self.skip = MODULES_TO_SKIP

        self.q_stdin = queue.Queue()
        self.q_stdout = queue.Queue()

        self.pdb = CustomizedPdb(
            proxy=self,
            stdin=StreamIn(self.q_stdin),
            stdout=StreamOut(self.q_stdout),
            skip=self.skip,
            readrc=False)

        self._trace_func_all = self.trace_func_all
        self._traces = []

        self._first = True

    def trace_func(self, frame, event, arg):
        """The main trace function

        This method will be called by the instance of Trace.
        The event should be always "call."
        """

        module_name = frame.f_globals.get('__name__')
        if self.pdb.is_skipped_module(module_name):
            return
        # print(module_name)

        if not event == 'call':
            warnings.warn('The event is not "call": ({}, {}, {})'.format(frame, event, arg))
        if self._first:
            return self.trace_func_outermost(frame, event, arg)
        return self.trace_func_all(frame, event, arg)

    def trace_func_outermost(self, frame, event, arg):
        """The trace function of the outermost scope in the thread or async task

        This method is used as a trace function of the outermost scope
        of the thread or async task. It is used to detect the end of
        the thread or async task.

        """
        if event == 'call':
            module_name = frame.f_globals.get('__name__')
            if not is_matched_to_any(module_name, self.modules_to_trace):
                return
            self._first = False
            self.registry.register_thread_task_id(self.thread_asynctask_id)
        if self._trace_func_all:
            self._trace_func_all = self._trace_func_all(frame, event, arg)
        if event == 'return':
            if asyncio.isfuture(arg):
                # awaiting. will be called again
                self._first = True
            else:
                self.trace.returning(self.thread_asynctask_id)
                self.registry.deregister_thread_task_id(self.thread_asynctask_id)
        return self.trace_func_outermost

    def trace_func_all(self, frame, event, arg):
        """The trace function that calls the trace function of pdb

        """

        module_name = frame.f_globals.get('__name__')
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        if self.pdb.is_skipped_module(module_name):
            # print(module_name)
            return

        func_name = frame.f_code.co_name
        # a function name
        # Note: '<module>' for the code produced by compile()
        if func_name == '<lambda>':
            return

        # print('{}.{}()'.format(module_name, func_name))
        # self.pdb.set_next(frame)

        trace = TraceBlock(
            thread_asynctask_id=self.thread_asynctask_id,
            pdb=self.pdb,
            registry=self.registry
        )
        self._traces.append(trace)
        return trace(frame, event, arg)

    def entering_cmdloop(self, frame, state):
        """called by the customized pdb before it is entering the command loop
        """
        module_name = frame.f_globals.get('__name__')
        self.modules_to_trace.add(module_name)

        self.registry.register_thread_task_state(self.thread_asynctask_id, state)

        self.pdb_ci = PdbCommandInterface(self.pdb, self.q_stdin, self.q_stdout)
        self.pdb_ci.start()
        self.ci_registry.add(self.thread_asynctask_id, self.pdb_ci)
        prompting = self.prompting_counter()
        self.registry.register_prompting(self.thread_asynctask_id, prompting)

    def exited_cmdloop(self):
        """called by the customized pdb after it has exited from the command loop
        """
        self.ci_registry.remove(self.thread_asynctask_id)
        self.registry.deregister_prompting(self.thread_asynctask_id)
        self.pdb_ci.end()

##__________________________________________________________________||
class TraceBlock:
    def __init__(self, thread_asynctask_id, pdb, registry):
        self.pdb = pdb
        self.trace_func = pdb.trace_dispatch
        self.registry = registry
        self.thread_asynctask_id = thread_asynctask_id

    def __call__(self, frame, event, arg):

        # if not frame.f_code.co_name == '<lambda>':
        #     file_name = self.pdb.canonic(frame.f_code.co_filename)
        #     line_no = frame.f_lineno
        #     self.registry.register_thread_task_state(self.thread_asynctask_id, file_name, line_no, event)

        if self.trace_func:
            self.trace_func = self.trace_func(frame, event, arg)
        return self

##__________________________________________________________________||
def is_matched_to_any(word, patterns):
    '''
    based on Bdb.is_skipped_module()
    https://github.com/python/cpython/blob/v3.9.5/Lib/bdb.py#L191
    '''
    if word is None:
        return False
    for pattern in patterns:
        if fnmatch.fnmatch(word, pattern):
            return True
    return False

##__________________________________________________________________||
