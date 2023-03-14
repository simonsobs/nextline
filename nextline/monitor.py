import asyncio

from apluggy import PluginManager

from .spawned import QueueOut
from .utils import to_thread

# from rich import print


class Monitor:
    def __init__(self, hook: PluginManager, queue: QueueOut):
        self._hook = hook
        self._queue = queue

    async def open(self):
        self._task = asyncio.create_task(self._monitor())

    async def close(self):
        await to_thread(self._queue.put, None)
        await self._task

    async def _monitor(self) -> None:
        while (event := await to_thread(self._queue.get)) is not None:
            print(event)
