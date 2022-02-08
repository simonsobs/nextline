import linecache

from .state import Machine


# __________________________________________________________________||
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
        self.machine = Machine(statement)
        self.registry = self.machine.registry

    def __repr__(self):
        # e.g., "<Nextline 'running'>"
        return f"<{self.__class__.__name__} {self.global_state!r}>"

    def run(self):
        """execute the script"""
        self.machine.run()

    async def finish(self):
        """wait until the script execution exits

        wait for the script execution in another thread to exit and
        join the thread.

        """
        await self.machine.finish()

    def exception(self):
        """uncaught exeption from the last run"""
        return self.machine.exception()

    def result(self):
        """return value of the last run. always None"""
        self.machine.result()

    def reset(self, statement=None):
        """prepare for run"""
        self.machine.reset(statement=statement)

    async def close(self):
        """end gracefully"""
        await self.machine.close()

    @property
    def statement(self) -> str:
        """The script"""
        return self.registry.get("statement")

    @property
    def global_state(self) -> str:
        """state, e.g., "initialized", "running", "exited", "finished", "closed" """
        return self.machine.state_name

    async def subscribe_global_state(self):
        # wish to be able to write with "yield from" but not possible
        # https://stackoverflow.com/a/59079548/7309855
        agen = self.registry.subscribe("state_name")
        async for y in agen:
            yield y

    @property
    def run_no(self):
        """The current run number"""
        return self.registry.get("run_no")

    async def subscribe_run_no(self):
        agen = self.registry.subscribe("run_no")
        async for y in agen:
            yield y

    async def subscribe_thread_asynctask_ids(self):
        agen = self.registry.subscribe("thread_task_ids")
        async for y in agen:
            yield y

    async def subscribe_thread_asynctask_state(self, thread_asynctask_id):
        agen = self.registry.subscribe(thread_asynctask_id)
        async for y in agen:
            yield y

    def send_pdb_command(self, thread_asynctask_id, command):
        self.machine.send_pdb_command(thread_asynctask_id, command)

    def get_source(self, file_name=None):
        if not file_name or file_name == self.registry.get("script_file_name"):
            return self.registry.get("statement").split("\n")
        return [e.rstrip() for e in linecache.getlines(file_name)]

    def get_source_line(self, line_no, file_name=None):
        """
        based on linecache.getline()
        https://github.com/python/cpython/blob/v3.9.5/Lib/linecache.py#L26
        """
        lines = self.get_source(file_name)
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ""


# __________________________________________________________________||
