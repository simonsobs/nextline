import threading
import asyncio
from pdb import Pdb

##__________________________________________________________________||
class Trace0:
    # created for the entry block of each asyncio task
    # used to trigger the end of the task

    def __init__(self, pdb_wrapper):
        self.pdb_wrapper = pdb_wrapper
        self.trace_dispatch = self.pdb_wrapper.trace_dispatch_wrapper

    def __call__(self, frame, event, arg):
        if self.trace_dispatch:
            self.trace_dispatch = self.trace_dispatch(frame, event, arg)
        if event == 'return':
            # the end of the task
            pass
        return self

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


class Trace:
    """A trace function which starts pdb in a new thread or async task

    An callable instance of this class should be set as the trace function by
    sys.settrace() and threading.settrace().

    """
    def __init__(self, thread_asynctask_regsitry, breaks):
        self.thread_asynctask_regsitry = thread_asynctask_regsitry
        self.breaks = breaks
        self.thread_asynctask_ids = set()

    def __call__(self, frame, event, arg):
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        module_name = frame.f_globals.get('__name__')
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        func_name = frame.f_code.co_name
        # '<module>' for the code produced by compile()

        if not func_name in self.breaks.get(module_name, []):
            return

        # print('Event: {}'.format(event))
        # print('Module name: {!r}'.format(module_name))
        # print('File name: {}'.format(frame.f_code.co_filename))
        # print('Line number: {}'.format(frame.f_lineno))
        # print('Function name: {!r}'.format(func_name))

        print('{}.{}()'.format(module_name, func_name))

        thread_asynctask_id = create_thread_asynctask_id()
        print(*thread_asynctask_id)

        local_control = self.thread_asynctask_regsitry.local_control(thread_asynctask_id)

        if thread_asynctask_id in self.thread_asynctask_ids:
            return local_control.pdb.trace_dispatch_wrapper(frame, event, arg)

        self.thread_asynctask_ids.add(thread_asynctask_id)

        trace0 = Trace0(local_control.pdb)
        return trace0(frame, event, arg)
        # return local_control.pdb.trace_dispatch_wrapper(frame, event, arg)

##__________________________________________________________________||
def create_thread_asynctask_id():
    """Return the pair of the current thread ID and async task ID

    Returns
    -------
    tuple
        The pair of the current thread ID and async task ID. If not in an
        async task, the async task ID will be None.

    """

    thread_id = threading.get_ident()

    asynctask_id = None
    try:
        asynctask_id = id(asyncio.current_task())
    except RuntimeError:
        # no running event loop
        pass

    return (thread_id, asynctask_id)

##__________________________________________________________________||
