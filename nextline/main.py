import threading

from .state import Initialized

##__________________________________________________________________||
class Nextline:
    """Nextline allows line-by-line execution of concurrent Python scripts

    Nextline supports concurrency with threading and asyncio. It uses
    multiple instances of Pdb, one for each thread and async task.

    Note
    ----
    The running asyncio event loop must exists when Nextline is
    instantiated.

    Parameters
    ----------
    statement : str
        A Python code as a string

    """

    def __init__(self, statement):
        self._event_run = threading.Event()

        self._state = Initialized(statement)
        self.registry = self._state.registry

    @property
    def global_state(self) -> str:
        """state, e.g., "initialized", "running", "finished"
        """
        return self._state.name

    def run(self):
        """run the script
        """
        self._state = self._state.run(exited=self._exited)
        self._event_run.set()

    def _exited(self, state):
        """callback function for the script execution

        This method is to be called by Running from the thread that
        executes the script when the execution has exited.

        """
        self._event_run.wait() # in case the script finishes too quickly
        self._event_run.clear()
        self._state = state

    async def wait(self):
        """wait for the script execution to finish
        """
        self._state = await self._state.wait()

    async def close(self):
        """close the nextline
        """
        self._state = await self._state.close()

    async def subscribe_global_state(self):
        # wish to be able to write with "yield from" but not possible
        # https://stackoverflow.com/a/59079548/7309855
        agen = self.registry.subscribe_state_name()
        async for y in agen:
            yield y

    async def subscribe_thread_asynctask_ids(self):
        agen = self.registry.subscribe_thread_task_ids()
        async for y in agen:
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        agen = self.registry.subscribe_thread_task_state(thread_asynctask_id)
        async for y in agen:
            yield y

    def send_pdb_command(self, thread_asynctask_id, command):
        self._state.send_pdb_command(thread_asynctask_id, command)

    def get_source(self, file_name=None):
        return self.registry.get_source(file_name=file_name)

    def get_source_line(self, line_no, file_name=None):
        return self.registry.get_source_line(line_no=line_no, file_name=file_name)

##__________________________________________________________________||
