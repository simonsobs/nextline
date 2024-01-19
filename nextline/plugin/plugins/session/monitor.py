import asyncio
import time
from logging import getLogger

from nextline import spawned
from nextline.plugin.spec import Context
from nextline.spawned import QueueOut

# from rich import print


class Monitor:
    def __init__(self, context: Context, queue: QueueOut):
        self._context = context
        self._queue = queue
        self._logger = getLogger(__name__)

    async def open(self) -> None:
        self._task = asyncio.create_task(self._monitor())

    async def close(self) -> None:
        up_to = 0.05
        start = time.process_time()
        while not self._queue.empty() and time.process_time() - start < up_to:
            await asyncio.sleep(0)
        await asyncio.to_thread(self._queue.put, None)  # type: ignore
        await self._task

    async def __aenter__(self) -> 'Monitor':
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):  # type: ignore
        del exc_type, exc_value, traceback
        await self.close()

    async def _monitor(self) -> None:
        while (event := await asyncio.to_thread(self._queue.get)) is not None:
            await self._on_event(event)

    async def _on_event(self, event: spawned.Event) -> None:
        context = self._context
        ahook = context.hook.ahook
        match event:
            case spawned.OnStartTrace():
                await ahook.on_start_trace(context=context, event=event)
            case spawned.OnEndTrace():
                await ahook.on_end_trace(context=context, event=event)
            case spawned.OnStartTraceCall():
                await ahook.on_start_trace_call(context=context, event=event)
            case spawned.OnEndTraceCall():
                await ahook.on_end_trace_call(context=context, event=event)
            case spawned.OnStartCmdloop():
                await ahook.on_start_cmdloop(context=context, event=event)
            case spawned.OnEndCmdloop():
                await ahook.on_end_cmdloop(context=context, event=event)
            case spawned.OnStartPrompt():
                await ahook.on_start_prompt(context=context, event=event)
            case spawned.OnEndPrompt():
                await ahook.on_end_prompt(context=context, event=event)
            case spawned.OnWriteStdout():
                await ahook.on_write_stdout(context=context, event=event)
            case _:
                self._logger.warning(f'Unknown event: {event!r}')
