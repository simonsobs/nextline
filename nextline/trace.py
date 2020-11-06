import threading
import asyncio
from pdb import Pdb

##__________________________________________________________________||
class PdbWrapper(Pdb):
    def __init__(self, local_control, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_control = local_control

        # self.quitting = True # not sure if necessary

        # stop at the first line
        self.botframe = None
        self._set_stopinfo(None, None)

        self.super_trace_dispatch = super().trace_dispatch
        print(self.super_trace_dispatch)

    def trace_dispatch_wrapper(self, frame, event, arg):
        if self.super_trace_dispatch:
            self.super_trace_dispatch = self.super_trace_dispatch(frame, event, arg)
            print(self.super_trace_dispatch)
        return self.trace_dispatch_wrapper

class Trace:
    def __init__(self, control, breaks):
        self.control = control
        self.breaks = breaks

    def __call__(self, frame, event, arg):

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

        thread_task_id = create_thread_task_id()
        print(*thread_task_id)

        local_control = self.control.local_control(thread_task_id)

        return local_control.pdb.trace_dispatch_wrapper(frame, event, arg)

##__________________________________________________________________||
def create_thread_task_id():

    thread_id = threading.get_ident()

    task_id = None
    try:
        task_id = id(asyncio.current_task())
    except RuntimeError:
        # no running event loop
        pass

    return (thread_id, task_id)

##__________________________________________________________________||
