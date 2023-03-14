from __future__ import annotations

import asyncio

from rich import print

from .spawned import QueueOut
from .utils import to_thread


class Monitor:
    def __init__(self, queue: QueueOut):
        self._queue = queue

    async def open(self):
        self._task = asyncio.create_task(self._monitor())

    async def close(self):
        await to_thread(self._queue.put, None)
        await self._task

    async def _monitor(self) -> None:
        while (event := await to_thread(self._queue.get)) is not None:
            print(event)
