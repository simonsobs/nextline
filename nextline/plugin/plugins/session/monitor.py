import asyncio
import time
from logging import getLogger

from apluggy import PluginManager

from nextline import spawned

from ....spawned import QueueOut
from ....utils import to_thread

# from rich import print


class Monitor:
    def __init__(self, hook: PluginManager, queue: QueueOut):
        self._hook = hook
        self._queue = queue
        self._logger = getLogger(__name__)

    async def open(self):
        self._task = asyncio.create_task(self._monitor())

    async def close(self) -> None:
        up_to = 0.05
        start = time.process_time()
        while not self._queue.empty() and time.process_time() - start < up_to:
            await asyncio.sleep(0)
        await to_thread(self._queue.put, None)
        await self._task

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        del exc_type, exc_value, traceback
        await self.close()

    async def _monitor(self) -> None:
        while (event := await to_thread(self._queue.get)) is not None:
            await self._on_event(event)

    async def _on_event(self, event: spawned.Event) -> None:
        if isinstance(event, spawned.OnStartTrace):
            await self._hook.ahook.on_start_trace(event=event)
        elif isinstance(event, spawned.OnEndTrace):
            await self._hook.ahook.on_end_trace(event=event)
        elif isinstance(event, spawned.OnStartTraceCall):
            await self._hook.ahook.on_start_trace_call(event=event)
        elif isinstance(event, spawned.OnEndTraceCall):
            await self._hook.ahook.on_end_trace_call(event=event)
        elif isinstance(event, spawned.OnStartCmdloop):
            await self._hook.ahook.on_start_cmdloop(event=event)
        elif isinstance(event, spawned.OnEndCmdloop):
            await self._hook.ahook.on_end_cmdloop(event=event)
        elif isinstance(event, spawned.OnStartPrompt):
            await self._hook.ahook.on_start_prompt(event=event)
        elif isinstance(event, spawned.OnEndPrompt):
            await self._hook.ahook.on_end_prompt(event=event)
        elif isinstance(event, spawned.OnWriteStdout):
            await self._hook.ahook.on_write_stdout(event=event)
        else:
            self._logger.warning(f'Unknown event: {event!r}')
