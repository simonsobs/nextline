import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger

from nextline import spawned
from nextline.plugin.spec import Context
from nextline.spawned import QueueOut


@asynccontextmanager
async def relay_queue(context: Context, queue: QueueOut) -> AsyncIterator[None]:
    task = asyncio.create_task(_monitor(context, queue))
    try:
        yield
    finally:
        up_to = 0.05
        start = time.process_time()
        while not queue.empty() and time.process_time() - start < up_to:
            await asyncio.sleep(0)
        await asyncio.to_thread(queue.put, None)  # type: ignore
        await task


async def _monitor(context: Context, queue: QueueOut) -> None:
    while (event := await asyncio.to_thread(queue.get)) is not None:
        await _on_event(context, event)


async def _on_event(context: Context, event: spawned.Event) -> None:
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
            logger = getLogger(__name__)
            logger.warning(f'Unknown event: {event!r}')
