import threading
import asyncio

##__________________________________________________________________||
class LocalTrace:
    def __init__(self, local_control):
        self.local_control = local_control

    def __call__(self, frame, event, arg):
        message = {'called': {'frame': frame, 'event': event, 'arg': arg}}
        while True:
            cmd = self.local_control(message)
            if cmd == 'next':
                return self
            else:
                message = {'message': 'unrecognized command {!r}'.format(cmd)}
        return self

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

        return local_control.pdb.trace_dispatch(frame, event, arg)

        # trace_local = LocalTrace(local_control)
        # 
        # return trace_local(frame, event, arg)

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
