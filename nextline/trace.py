import threading
import asyncio

from .pdb.proxy import PdbProxy

##__________________________________________________________________||
class Trace:
    """A trace function which starts pdb in a new thread or async task

    An callable instance of this class should be set as the trace function by
    sys.settrace() and threading.settrace().

    """
    def __init__(self, statement, breaks):
        self.statement = statement
        self.breaks = breaks
        self.condition = threading.Condition()
        self.pdb_proxies = {}
        self.pdb_cis = []

    def __call__(self, frame, event, arg):
        """Called by the Python interpreter when a new local scope is entered.

        https://docs.python.org/3/library/sys.html#sys.settrace

        """

        module_name = frame.f_globals.get('__name__')
        # e.g., 'threading', '__main__', 'concurrent.futures.thread', 'asyncio.events'

        func_name = frame.f_code.co_name
        # '<module>' for the code produced by compile()

        if not func_name in self.breaks.get(module_name, []):
            # print('{}.{}()'.format(module_name, func_name))
            return

        # print('Event: {}'.format(event))
        # print('Module name: {!r}'.format(module_name))
        # print('File name: {}'.format(frame.f_code.co_filename))
        # print('Line number: {}'.format(frame.f_lineno))
        # print('Function name: {!r}'.format(func_name))

        print('{}.{}()'.format(module_name, func_name))

        thread_asynctask_id = compose_thread_asynctask_id()
        print(*thread_asynctask_id)

        if pdb_proxy := self.pdb_proxies.get(thread_asynctask_id):
            return pdb_proxy.trace_func(frame, event, arg)

        pdb_proxy = PdbProxy(thread_asynctask_id=thread_asynctask_id, trace=self)
        self.pdb_proxies[thread_asynctask_id] = pdb_proxy
        return pdb_proxy.trace_func_init(frame, event, arg)

    def enter_cmdloop(self, pdb_ci):
        with self.condition:
            self.pdb_cis.append(pdb_ci)

    def exit_cmdloop(self, pdb_ci):
        with self.condition:
            self.pdb_cis.remove(pdb_ci)

    def nthreads(self):
        with self.condition:
            return len({i for i, _ in self.pdb_proxies.keys()})

##__________________________________________________________________||
def compose_thread_asynctask_id():
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
